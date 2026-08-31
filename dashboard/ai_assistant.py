"""
AI Business Assistant.

If ANTHROPIC_API_KEY is set in your .env, questions are answered by
Claude using your shop's live data as context (real AI).

If no API key is set, a lightweight rule-based fallback still answers
common questions (best seller, low stock, today's sales, udhaar due)
by reading the same data directly - so the assistant still works out
of the box for a demo, without needing any paid API key.
"""
import os
import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, F


def gather_shop_context(shop):
    from inventory.models import Product
    from billing.models import Bill, BillItem
    from udhaar.models import Customer

    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)

    products = Product.objects.filter(shop=shop)
    low_stock = list(products.filter(stock_qty__lte=F("low_stock_threshold")).values_list("name", "stock_qty"))

    recent_bills = Bill.objects.filter(shop=shop, date__gte=week_ago)
    total_sales_week = float(recent_bills.aggregate(Sum("total_amount"))["total_amount__sum"] or 0)

    today_bills = Bill.objects.filter(shop=shop, date__date=today)
    total_sales_today = float(today_bills.aggregate(Sum("total_amount"))["total_amount__sum"] or 0)

    top_items = (
        BillItem.objects.filter(bill__shop=shop, bill__date__gte=week_ago)
        .values("product_name_snapshot")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:5]
    )

    customers = Customer.objects.filter(shop=shop)
    total_udhaar = sum(c.total_due for c in customers)
    top_debtors = sorted(customers, key=lambda c: c.total_due, reverse=True)[:5]

    return {
        "shop_name": shop.name,
        "low_stock_products": low_stock,
        "total_sales_last_7_days": total_sales_week,
        "total_sales_today": total_sales_today,
        "top_selling_products_last_7_days": [
            {"name": i["product_name_snapshot"], "qty_sold": i["total_qty"]} for i in top_items
        ],
        "total_pending_udhaar": total_udhaar,
        "top_debtors": [{"name": c.name, "due": c.total_due} for c in top_debtors if c.total_due > 0],
        "total_products": products.count(),
    }


def _fallback_answer(question: str, ctx: dict) -> str:
    q = question.lower()
    if "low stock" in q or "khatam" in q or "stock kam" in q:
        if ctx["low_stock_products"]:
            items = ", ".join(f"{n} ({q_})" for n, q_ in ctx["low_stock_products"])
            return f"These products are running low: {items}. Consider restocking soon."
        return "No products are low on stock right now. You're well stocked!"
    if "best sell" in q or "top product" in q or "sabse zyada" in q:
        if ctx["top_selling_products_last_7_days"]:
            top = ctx["top_selling_products_last_7_days"][0]
            return f"Your best seller this week is {top['name']} with {top['qty_sold']} units sold."
        return "No sales recorded in the last 7 days yet."
    if "today" in q or "aaj" in q:
        return f"Today's total sales so far: Rs.{ctx['total_sales_today']}."
    if "udhaar" in q or "due" in q or "credit" in q:
        if ctx["top_debtors"]:
            names = ", ".join(f"{d['name']} (Rs.{d['due']})" for d in ctx["top_debtors"])
            return f"Total pending udhaar: Rs.{ctx['total_pending_udhaar']}. Top dues: {names}."
        return "No pending udhaar right now. All clear!"
    if "week" in q or "hafte" in q:
        return f"Total sales in the last 7 days: Rs.{ctx['total_sales_last_7_days']}."
    return (
        f"I can tell you about sales, low stock, best sellers, and udhaar for {ctx['shop_name']}. "
        f"Try asking things like 'what's low on stock?' or 'who owes me the most?'. "
        f"(Add an ANTHROPIC_API_KEY in .env for smarter, open-ended answers.)"
    )


def ask_assistant(shop, question: str) -> str:
    ctx = gather_shop_context(shop)
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return _fallback_answer(question, ctx)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = (
            "You are a helpful business assistant for a small Indian retail shop. "
            "Answer the owner's question using ONLY the JSON data provided below. "
            "Be concise (2-4 sentences), practical, and friendly. Use Rs. for currency.\n\n"
            f"Shop data:\n{json.dumps(ctx, indent=2)}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text
    except Exception as e:
        return _fallback_answer(question, ctx) + f"\n\n(AI call failed, showing basic answer instead: {e})"
