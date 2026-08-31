import json
import urllib.parse
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Sum
from inventory.models import Product
from udhaar.models import Customer, UdhaarTransaction
from accounts.utils import log_activity
from .models import Bill, BillItem, BillReturn, BillReturnItem, CashRegister
from .utils import send_whatsapp_message, build_bill_message


@login_required
def bill_create(request):
    shop = request.user.profile.shop
    products = Product.objects.filter(shop=shop)
    categories = list(Product.objects.filter(shop=shop).values_list("category", flat=True).distinct())
    categories = [c for c in categories if c]

    if request.method == "POST":
        items_json = request.POST.get("items_json", "[]")
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            items = []

        if not items:
            messages.error(request, "Please add at least one product to the bill.")
            return redirect("billing:bill_create")

        discount = Decimal(request.POST.get("discount") or 0)
        gst_percent = Decimal(request.POST.get("gst_percent") or 0)
        payment_mode = request.POST.get("payment_mode", "cash")
        customer_name = request.POST.get("customer_name", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        redeem_points = int(request.POST.get("redeem_points") or 0)

        customer = None
        if customer_phone:
            customer, _ = Customer.objects.get_or_create(
                shop=shop, phone=customer_phone, defaults={"name": customer_name or "Customer"}
            )
            if customer_name and customer.name != customer_name:
                customer.name = customer_name
                customer.save()

        # Handle loyalty points redemption (1 point = Rs. 1 discount)
        points_discount = Decimal("0")
        actual_points_redeemed = 0
        if customer and redeem_points > 0:
            actual_points_redeemed = min(redeem_points, customer.loyalty_points)
            points_discount = Decimal(str(actual_points_redeemed))
            discount += points_discount

        subtotal = Decimal("0")
        bill = Bill.objects.create(
            shop=shop, customer=customer,
            customer_name_snapshot=customer_name, customer_phone_snapshot=customer_phone,
            discount=discount, gst_percent=gst_percent, payment_mode=payment_mode,
            points_redeemed=actual_points_redeemed,
        )

        anomalies_detected = []

        for item in items:
            try:
                product = Product.objects.get(id=item["product_id"], shop=shop)
            except (Product.DoesNotExist, KeyError):
                continue
            qty = int(item.get("qty", 0))
            if qty <= 0:
                continue

            custom_price = item.get("custom_price")
            if custom_price is not None and str(custom_price).strip() != "":
                price_at_sale = Decimal(str(custom_price))
                standard_price = Decimal(str(product.selling_price))
                if standard_price > 0:
                    diff_pct = abs(price_at_sale - standard_price) / standard_price * 100
                    if diff_pct >= 30:
                        anomalies_detected.append(
                            f"{product.name}: Standard Rs. {standard_price} vs Billed Rs. {price_at_sale} ({round(diff_pct)}% difference)"
                        )
            else:
                price_at_sale = Decimal(str(product.selling_price))

            line_total = price_at_sale * qty
            subtotal += line_total
            BillItem.objects.create(
                bill=bill, product=product, product_name_snapshot=product.name,
                quantity=qty, price_at_sale=price_at_sale,
            )
            product.stock_qty = max(0, product.stock_qty - qty)
            product.save()

        gst_amount = subtotal * (gst_percent / 100)
        total = subtotal - discount + gst_amount
        bill.subtotal = subtotal
        bill.total_amount = max(Decimal("0"), total)

        # Calculate Loyalty Points Earned (1 point per Rs. 100 spent)
        points_earned = int(bill.total_amount // 100)
        bill.points_earned = points_earned
        bill.save()

        # Update Customer Loyalty Ledger
        if customer:
            customer.loyalty_points = max(0, customer.loyalty_points - actual_points_redeemed + points_earned)
            customer.save()

        # Check high discount anomaly (>25%)
        if subtotal > 0 and (discount / subtotal * 100) >= 25:
            anomalies_detected.append(f"High Discount Applied: Rs. {discount} ({round(discount/subtotal*100)}% of total)")

        if payment_mode == "udhaar" and customer:
            UdhaarTransaction.objects.create(
                customer=customer, bill=bill, amount=bill.total_amount,
                type="credit_given", note=f"Bill #{bill.id}",
            )

        # Audit logging
        audit_details = f"Amount: Rs. {bill.total_amount}, Mode: {payment_mode}, Items: {len(items)}, Points Earned: {points_earned}"
        if anomalies_detected:
            audit_details += f" | ANOMALIES FLAGGED: {'; '.join(anomalies_detected)}"

        log_activity(
            shop, request.user, "create", "billing",
            f"Bill #{bill.id} ({customer_name or 'Walk-in'})",
            audit_details
        )

        if customer_phone:
            sent = send_whatsapp_message(customer_phone, build_bill_message(bill))
            bill.whatsapp_sent = sent
            bill.save()

        if anomalies_detected:
            messages.warning(request, f"Bill #{bill.id} created with Price Anomaly Notice: {'; '.join(anomalies_detected)}")
        else:
            messages.success(request, f"Bill #{bill.id} generated successfully!")
        return redirect("billing:bill_detail", pk=bill.id)

    return render(request, "billing/bill_create.html", {
        "products": products,
        "categories": categories,
        "shop": shop,
    })


@login_required
def customer_lookup_api(request):
    """API to lookup customer loyalty points and previous name by phone."""
    phone = request.GET.get("phone", "").strip()
    shop = request.user.profile.shop
    if not phone:
        return JsonResponse({"found": False})

    customer = Customer.objects.filter(shop=shop, phone=phone).first()
    if customer:
        return JsonResponse({
            "found": True,
            "name": customer.name,
            "points": customer.loyalty_points,
            "total_due": customer.total_due,
        })
    return JsonResponse({"found": False})


@login_required
def bill_list(request):
    shop = request.user.profile.shop
    bills = Bill.objects.filter(shop=shop)
    query = request.GET.get("q", "").strip()
    payment_filter = request.GET.get("payment_mode", "")

    if query:
        bills = bills.filter(
            Q(id__icontains=query) |
            Q(customer_name_snapshot__icontains=query) |
            Q(customer_phone_snapshot__icontains=query)
        )
    if payment_filter:
        bills = bills.filter(payment_mode=payment_filter)

    paginator = Paginator(bills, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "billing/bill_list.html", {
        "bills": page_obj,
        "page_obj": page_obj,
        "query": query,
        "payment_filter": payment_filter,
    })


@login_required
def bill_detail(request, pk):
    shop = request.user.profile.shop
    bill = get_object_or_404(Bill, pk=pk, shop=shop)

    # Build direct 1-click WhatsApp Web share link
    bill_text = f"🏪 *{shop.name}*\n"
    bill_text += f"🧾 *Invoice #{bill.id}* - {bill.date.strftime('%d-%m-%Y %I:%M %p')}\n"
    bill_text += f"Customer: {bill.customer_name_snapshot or 'Valued Customer'}\n"
    bill_text += "-------------------------\n"
    for item in bill.items.all():
        bill_text += f"• {item.product_name_snapshot} x{item.quantity} = Rs. {item.line_total}\n"
    bill_text += "-------------------------\n"
    bill_text += f"Subtotal: Rs. {bill.subtotal}\n"
    if bill.discount > 0:
        bill_text += f"Discount: -Rs. {bill.discount}\n"
    if bill.gst_percent > 0:
        bill_text += f"GST ({bill.gst_percent}%): +Rs. {bill.gst_amount}\n"
    bill_text += f"💰 *Grand Total: Rs. {bill.total_amount}* ({bill.get_payment_mode_display()})\n"
    if bill.points_earned > 0:
        bill_text += f"🎁 Loyalty Points Earned: +{bill.points_earned} pts\n"
    bill_text += f"\nThank you for shopping with us! Visit again. ✨"

    encoded_text = urllib.parse.quote(bill_text)
    clean_phone = "".join(filter(str.isdigit, bill.customer_phone_snapshot or ""))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_text}" if clean_phone else f"https://wa.me/?text={encoded_text}"

    return render(request, "billing/bill_detail.html", {
        "bill": bill,
        "whatsapp_url": whatsapp_url,
    })


@login_required
def bill_thermal(request, pk):
    """58mm / 80mm thermal receipt slip view."""
    shop = request.user.profile.shop
    bill = get_object_or_404(Bill, pk=pk, shop=shop)
    return render(request, "billing/bill_thermal.html", {"bill": bill, "shop": shop})


@login_required
def bill_pdf(request, pk):
    bill = get_object_or_404(Bill, pk=pk, shop=request.user.profile.shop)
    html = render_to_string("billing/bill_pdf.html", {"bill": bill})
    try:
        from xhtml2pdf import pisa
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="bill_{bill.id}.pdf"'
        pisa.CreatePDF(html, dest=response)
        return response
    except ImportError:
        return HttpResponse(html)


@login_required
def bill_return_create(request, pk):
    shop = request.user.profile.shop
    bill = get_object_or_404(Bill, pk=pk, shop=shop)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        refund_total = Decimal("0")
        return_items_data = []

        for item in bill.items.all():
            return_qty_str = request.POST.get(f"return_qty_{item.id}", "0")
            try:
                return_qty = int(return_qty_str)
            except ValueError:
                return_qty = 0

            if return_qty > 0 and return_qty <= item.quantity:
                line_refund = item.price_at_sale * return_qty
                refund_total += line_refund
                return_items_data.append((item, return_qty, item.price_at_sale, line_refund))

        if not return_items_data:
            messages.error(request, "Please specify valid return quantities for at least one item.")
            return redirect("billing:bill_return_create", pk=bill.id)

        return_record = BillReturn.objects.create(
            bill=bill,
            shop=shop,
            refund_amount=refund_total,
            reason=reason or "Customer returned items",
            created_by=request.user,
        )

        for item, return_qty, refund_rate, subtotal in return_items_data:
            BillReturnItem.objects.create(
                return_record=return_record,
                product=item.product,
                quantity=return_qty,
                refund_rate=refund_rate,
                subtotal=subtotal,
            )
            if item.product:
                item.product.stock_qty += return_qty
                item.product.save()

        if bill.payment_mode == "udhaar" and bill.customer:
            UdhaarTransaction.objects.create(
                customer=bill.customer,
                bill=bill,
                amount=refund_total,
                type="payment_received",
                note=f"Return Credit Adjustment for Bill #{bill.id}",
            )

        log_activity(
            shop, request.user, "return", "billing",
            f"Return for Bill #{bill.id}",
            f"Refund: Rs. {refund_total}, Restocked items: {len(return_items_data)}, Reason: {reason}"
        )

        messages.success(request, f"Successfully processed return of Rs. {refund_total}. Stock restored!")
        return redirect("billing:bill_detail", pk=bill.id)

    return render(request, "billing/bill_return_form.html", {"bill": bill})


@login_required
def bill_return_list(request):
    shop = request.user.profile.shop
    returns = BillReturn.objects.filter(shop=shop)
    paginator = Paginator(returns, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "billing/bill_return_list.html", {"returns": page_obj, "page_obj": page_obj})


@login_required
def cash_register_view(request):
    shop = request.user.profile.shop
    today = timezone.localdate()
    register = CashRegister.objects.filter(shop=shop, date=today).first()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "open":
            opening_cash = Decimal(request.POST.get("opening_cash") or 0)
            notes = request.POST.get("notes", "").strip()
            if not register:
                register = CashRegister.objects.create(
                    shop=shop,
                    date=today,
                    opening_cash=opening_cash,
                    status="open",
                    opened_by=request.user,
                    notes=notes,
                )
                log_activity(shop, request.user, "cash_register", "cash_register", f"Opened Drawer ({today})", f"Opening Cash: Rs. {opening_cash}")
                messages.success(request, f"Cash register opened with Rs. {opening_cash}.")
            return redirect("billing:cash_register")

        elif action == "cash_in_out":
            if register and register.status == "open":
                entry_type = request.POST.get("entry_type")
                amount = Decimal(request.POST.get("amount") or 0)
                reason = request.POST.get("reason", "").strip()
                if amount > 0:
                    if entry_type == "in":
                        register.cash_in += amount
                        log_activity(shop, request.user, "cash_register", "cash_register", "Cash Added (In)", f"Rs. {amount} - {reason}")
                        messages.success(request, f"Added Rs. {amount} cash in drawer.")
                    else:
                        register.cash_out += amount
                        log_activity(shop, request.user, "cash_register", "cash_register", "Cash Expense (Out)", f"Rs. {amount} - {reason}")
                        messages.success(request, f"Recorded Rs. {amount} cash withdrawal/expense.")
                    register.save()
            return redirect("billing:cash_register")

        elif action == "close":
            if register and register.status == "open":
                actual_closing = Decimal(request.POST.get("actual_closing") or 0)
                notes = request.POST.get("notes", "").strip()

                cash_sales = Bill.objects.filter(
                    shop=shop, payment_mode="cash", date__date=today
                ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")

                expected = register.opening_cash + cash_sales + register.cash_in - register.cash_out
                discrepancy = actual_closing - expected

                register.expected_closing = expected
                register.actual_closing = actual_closing
                register.discrepancy = discrepancy
                register.status = "closed"
                register.closed_by = request.user
                register.closed_at = timezone.now()
                if notes:
                    register.notes += f"\nClosing note: {notes}"
                register.save()

                disc_text = f"Exact Match (Rs. 0)" if discrepancy == 0 else f"{'Excess' if discrepancy > 0 else 'Shortage'} of Rs. {abs(discrepancy)}"
                log_activity(
                    shop, request.user, "cash_register", "cash_register",
                    f"Closed Drawer ({today})",
                    f"Expected: Rs. {expected}, Actual: Rs. {actual_closing}, Discrepancy: {disc_text}"
                )
                messages.success(request, f"Cash register closed for {today}. Discrepancy: {disc_text}.")
            return redirect("billing:cash_register")

    cash_sales = Decimal("0")
    if register:
        cash_sales = Bill.objects.filter(
            shop=shop, payment_mode="cash", date__date=today
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0")
        register.expected_closing = register.opening_cash + cash_sales + register.cash_in - register.cash_out

    return render(request, "billing/cash_register.html", {
        "register": register,
        "today": today,
        "cash_sales": cash_sales,
    })


@login_required
def cash_register_history(request):
    shop = request.user.profile.shop
    registers = CashRegister.objects.filter(shop=shop)
    paginator = Paginator(registers, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "billing/cash_register_history.html", {"registers": page_obj, "page_obj": page_obj})


@login_required
def product_price_api(request, pk):
    product = get_object_or_404(Product, pk=pk, shop=request.user.profile.shop)
    return JsonResponse({
        "name": product.name, "price": float(product.selling_price),
        "stock": product.stock_qty, "unit": product.unit,
    })
