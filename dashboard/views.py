import csv
import json
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Sum, F, Count
from django.views.decorators.csrf import csrf_exempt
from inventory.models import Product
from billing.models import Bill, BillItem
from udhaar.models import Customer
from accounts.utils import log_activity
from .ai_assistant import ask_assistant


@login_required
def home(request):
    shop = request.user.profile.shop
    today = timezone.localdate()
    seven_days_ago = timezone.now() - timedelta(days=7)
    thirty_days_ago = timezone.now() - timedelta(days=30)

    products = Product.objects.filter(shop=shop)
    low_stock = products.filter(stock_qty__lte=F("low_stock_threshold"))

    today_bills = Bill.objects.filter(shop=shop, date__date=today)
    today_total = today_bills.aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")

    customers = Customer.objects.filter(shop=shop)
    total_udhaar = sum(c.total_due for c in customers)

    # Last 7 days trend
    last_7_days = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_total = Bill.objects.filter(shop=shop, date__date=day).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")
        last_7_days.append({"date": day.strftime("%d %b"), "total": float(day_total)})

    # Payment Methods Split (Doughnut Chart)
    all_recent_bills = Bill.objects.filter(shop=shop, date__gte=thirty_days_ago)
    cash_total = float(all_recent_bills.filter(payment_mode="cash").aggregate(Sum("total_amount"))["total_amount__sum"] or 0)
    upi_total = float(all_recent_bills.filter(payment_mode="upi").aggregate(Sum("total_amount"))["total_amount__sum"] or 0)
    card_total = float(all_recent_bills.filter(payment_mode="card").aggregate(Sum("total_amount"))["total_amount__sum"] or 0)
    udhaar_total = float(all_recent_bills.filter(payment_mode="udhaar").aggregate(Sum("total_amount"))["total_amount__sum"] or 0)

    payment_chart_labels = ["Cash", "UPI / QR", "Card", "Udhaar"]
    payment_chart_data = [cash_total, upi_total, card_total, udhaar_total]

    # Hourly Rush Hour Heatmap (08:00 to 22:00)
    hourly_distribution = [0] * 15  # 8 AM to 10 PM
    for b in all_recent_bills:
        hour = b.date.hour
        if 8 <= hour <= 22:
            hourly_distribution[hour - 8] += 1

    hourly_labels = [f"{h}:00" for h in range(8, 23)]

    # Top selling items in last 30 days
    top_items = (
        BillItem.objects.filter(bill__shop=shop, bill__date__gte=thirty_days_ago)
        .values("product_name_snapshot")
        .annotate(total_qty=Sum("quantity"), total_revenue=Sum(F("quantity") * F("price_at_sale")))
        .order_by("-total_qty")[:5]
    )

    # Top Loyal Customers (Loyalty Rewards Leaderboard)
    top_loyal_customers = Customer.objects.filter(shop=shop, loyalty_points__gt=0).order_by("-loyalty_points")[:5]

    # 30-Day Velocity & Smart Restock Predictions
    sales_30d = (
        BillItem.objects.filter(bill__shop=shop, bill__date__gte=thirty_days_ago)
        .values("product_id")
        .annotate(total_sold=Sum("quantity"))
    )
    sales_map = {item["product_id"]: item["total_sold"] for item in sales_30d}

    critical_restock_list = []
    for p in products:
        sold_30d = sales_map.get(p.id, 0)
        daily_rate = sold_30d / 30.0 if sold_30d > 0 else 0.0
        if daily_rate > 0:
            days_left = round(p.stock_qty / daily_rate, 1)
            if days_left <= 5:
                p.days_left = days_left
                p.daily_rate = round(daily_rate, 1)
                critical_restock_list.append(p)
        elif p.is_low_stock:
            p.days_left = 0
            p.daily_rate = 0
            critical_restock_list.append(p)

    critical_restock_list = sorted(critical_restock_list, key=lambda x: x.days_left if x.days_left is not None else 999)[:6]

    # Calculate Real-Time 30-Day Net Profit & Margin
    bill_items_30d = BillItem.objects.filter(bill__shop=shop, bill__date__gte=thirty_days_ago).select_related("product")
    total_revenue_30d = sum((item.quantity * item.price_at_sale for item in bill_items_30d), Decimal("0"))
    total_cogs_30d = sum((item.quantity * (item.product.cost_price if item.product else Decimal("0")) for item in bill_items_30d), Decimal("0"))
    gross_profit_30d = total_revenue_30d - total_cogs_30d

    from billing.models import CashRegister
    cash_expenses_30d = CashRegister.objects.filter(shop=shop, date__gte=thirty_days_ago.date()).aggregate(Sum("cash_out"))["cash_out__sum"] or Decimal("0")
    net_profit_30d = gross_profit_30d - cash_expenses_30d
    profit_margin_30d = round((float(gross_profit_30d) / float(total_revenue_30d) * 100), 1) if total_revenue_30d > 0 else 0.0

    # Top Profitable Products in 30 Days (Ranked by Rupee Profit Margin)
    product_profit_map = {}
    for item in bill_items_30d:
        p_name = item.product_name_snapshot
        cost = item.product.cost_price if item.product else Decimal("0")
        item_profit = (item.price_at_sale - cost) * item.quantity
        if p_name not in product_profit_map:
            product_profit_map[p_name] = {"qty": 0, "revenue": Decimal("0"), "profit": Decimal("0")}
        product_profit_map[p_name]["qty"] += item.quantity
        product_profit_map[p_name]["revenue"] += (item.price_at_sale * item.quantity)
        product_profit_map[p_name]["profit"] += item_profit

    top_profitable_items = sorted(
        [{"name": k, "qty": v["qty"], "revenue": v["revenue"], "profit": v["profit"]} for k, v in product_profit_map.items()],
        key=lambda x: x["profit"],
        reverse=True
    )[:5]

    # Near-Expiry Products (Expiring in <= 30 days)
    near_expiry_products = products.filter(expiry_date__isnull=False, expiry_date__lte=today + timedelta(days=30), expiry_date__gte=today).order_by("expiry_date")[:5]

    # Dead Stock & Idle Capital Locker (Products with 0 sales in 30 days)
    dead_stock_items = [p for p in products if p.id not in sales_map and p.stock_qty > 0][:6]
    dead_stock_capital = sum((p.stock_qty * p.cost_price for p in dead_stock_items), Decimal("0"))

    # Weekly Auto-Summary Calculation
    week_bills = Bill.objects.filter(shop=shop, date__gte=seven_days_ago)
    week_total = week_bills.aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")
    week_bill_count = week_bills.count()

    top_week_item = (
        BillItem.objects.filter(bill__shop=shop, bill__date__gte=seven_days_ago)
        .values("product_name_snapshot")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")
        .first()
    )
    top_week_product_name = top_week_item["product_name_snapshot"] if top_week_item else "N/A"
    top_week_product_qty = top_week_item["qty"] if top_week_item else 0

    cash_week = week_bills.filter(payment_mode="cash").aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")
    upi_week = week_bills.filter(payment_mode="upi").aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")
    udhaar_week = week_bills.filter(payment_mode="udhaar").aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")

    weekly_summary = (
        f"In the past 7 days, your store generated Rs. {week_total:,.2f} across {week_bill_count} bills. "
        f"Top product was '{top_week_product_name}' with {top_week_product_qty} units sold. "
        f"Payment collection: Cash: Rs. {cash_week:,.0f}, UPI: Rs. {upi_week:,.0f}, Udhaar: Rs. {udhaar_week:,.0f}. "
        f"Net Profit (30D): Rs. {net_profit_30d:,.2f} ({profit_margin_30d}% Margin). "
        f"{len(critical_restock_list)} items need reordering within 5 days."
    )

    context = {
        "shop": shop,
        "today_total": today_total,
        "total_products": products.count(),
        "low_stock_count": low_stock.count(),
        "low_stock_products": low_stock[:6],
        "total_udhaar": total_udhaar,
        "net_profit_30d": net_profit_30d,
        "gross_profit_30d": gross_profit_30d,
        "profit_margin_30d": profit_margin_30d,
        "top_profitable_items": top_profitable_items,
        "near_expiry_products": near_expiry_products,
        "dead_stock_items": dead_stock_items,
        "dead_stock_capital": dead_stock_capital,
        "recent_bills": Bill.objects.filter(shop=shop)[:5],
        "chart_labels": json.dumps([d["date"] for d in last_7_days]),
        "chart_data": json.dumps([d["total"] for d in last_7_days]),
        "payment_labels": json.dumps(payment_chart_labels),
        "payment_data": json.dumps(payment_chart_data),
        "hourly_labels": json.dumps(hourly_labels),
        "hourly_data": json.dumps(hourly_distribution),
        "top_items": top_items,
        "top_loyal_customers": top_loyal_customers,
        "weekly_summary": weekly_summary,
        "week_total": week_total,
        "week_bill_count": week_bill_count,
        "critical_restock_list": critical_restock_list,
    }
    return render(request, "dashboard/home.html", context)


# --- 🌐 Public Zero-Commission Online Storefront & WhatsApp Ordering ---

def public_storefront(request, shop_id):
    """Public customer shopping catalog for mobile & web ordering via WhatsApp."""
    from accounts.models import Shop
    from django.shortcuts import get_object_or_404
    shop = get_object_or_404(Shop, id=shop_id)
    products = Product.objects.filter(shop=shop, stock_qty__gt=0).order_by("category", "name")

    category = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()

    if category:
        products = products.filter(category=category)
    if query:
        products = products.filter(name__icontains=query)

    categories = Product.objects.filter(shop=shop, stock_qty__gt=0).values_list("category", flat=True).distinct()
    categories = [c for c in categories if c]

    owner_profile = getattr(shop.owner, "profile", None)
    shop_phone = owner_profile.phone if owner_profile and owner_profile.phone else "9876543210"
    # Clean phone for wa.me link
    clean_phone = "".join(filter(str.isdigit, shop_phone))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    return render(request, "dashboard/public_storefront.html", {
        "shop": shop,
        "products": products,
        "categories": categories,
        "selected_category": category,
        "query": query,
        "shop_phone": clean_phone,
        "display_phone": shop_phone,
    })


@login_required
def store_qr_standee(request, shop_id):
    """Printable Counter QR Standee Flyer for the shopkeeper."""
    from accounts.models import Shop
    from django.shortcuts import get_object_or_404
    from django.urls import reverse
    shop = get_object_or_404(Shop, id=shop_id)

    store_path = reverse("dashboard:public_storefront", args=[shop.id])
    store_url = request.build_absolute_uri(store_path)

    owner_profile = getattr(shop.owner, "profile", None)
    shop_phone = owner_profile.phone if owner_profile and owner_profile.phone else ""

    return render(request, "dashboard/store_qr_standee.html", {
        "shop": shop,
        "store_url": store_url,
        "shop_phone": shop_phone,
    })



@login_required
def ai_chat(request):
    return render(request, "dashboard/ai_chat.html")


@login_required
def ai_ask_api(request):
    if request.method == "POST":
        data = json.loads(request.body or "{}")
        question = data.get("question", "").strip()
        if not question:
            return JsonResponse({"answer": "Please type a question."})
        answer = ask_assistant(request.user.profile.shop, question)
        return JsonResponse({"answer": answer})
    return JsonResponse({"error": "POST required"}, status=400)


# --- Data Export Endpoints (Excel / CSV) ---

@login_required
def export_sales_csv(request):
    shop = request.user.profile.shop
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"sales_report_{shop.name.lower().replace(' ', '_')}_{timezone.localdate()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Bill ID", "Date & Time", "Customer Name", "Customer Phone", "Payment Mode", "Subtotal (Rs.)", "Discount (Rs.)", "GST %", "Total Amount (Rs.)", "Points Earned"])

    bills = Bill.objects.filter(shop=shop).order_by("-date")
    for b in bills:
        writer.writerow([
            b.id,
            b.date.strftime("%Y-%m-%d %H:%M"),
            b.customer_name_snapshot or "Walk-in",
            b.customer_phone_snapshot or "",
            b.get_payment_mode_display(),
            b.subtotal,
            b.discount,
            b.gst_percent,
            b.total_amount,
            b.points_earned,
        ])

    log_activity(shop, request.user, "export", "billing", "Exported Sales CSV", f"Exported {bills.count()} bills")
    return response


@login_required
def export_inventory_csv(request):
    shop = request.user.profile.shop
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"inventory_{shop.name.lower().replace(' ', '_')}_{timezone.localdate()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Product ID", "Product Name", "Category", "Cost Price (Rs.)", "Selling Price (Rs.)", "Current Stock", "Unit", "Stock Alert Threshold", "Expiry Date"])

    products = Product.objects.filter(shop=shop).order_by("category", "name")
    for p in products:
        writer.writerow([
            p.id,
            p.name,
            p.category or "General",
            p.cost_price,
            p.selling_price,
            p.stock_qty,
            p.get_unit_display(),
            p.low_stock_threshold,
            p.expiry_date.strftime("%Y-%m-%d") if p.expiry_date else "",
        ])

    log_activity(shop, request.user, "export", "inventory", "Exported Inventory CSV", f"Exported {products.count()} products")
    return response


@login_required
def export_customers_csv(request):
    shop = request.user.profile.shop
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"udhaar_customers_{shop.name.lower().replace(' ', '_')}_{timezone.localdate()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Customer Name", "Phone Number", "Loyalty Reward Points", "Total Credit Taken (Rs.)", "Total Paid (Rs.)", "Pending Due Balance (Rs.)", "Account Created"])

    customers = Customer.objects.filter(shop=shop).order_by("name")
    for c in customers:
        credit = c.transactions.filter(type="credit_given").aggregate(Sum("amount"))["amount__sum"] or 0
        paid = c.transactions.filter(type="payment_received").aggregate(Sum("amount"))["amount__sum"] or 0
        writer.writerow([
            c.name,
            c.phone,
            c.loyalty_points,
            credit,
            paid,
            c.total_due,
            c.created_at.strftime("%Y-%m-%d"),
        ])

    log_activity(shop, request.user, "export", "udhaar", "Exported Customer Udhaar CSV", f"Exported {customers.count()} customers")
    return response
