import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from inventory.models import Product
from accounts.utils import log_activity
from .models import Supplier, Purchase, PurchaseItem, SupplierPayment
from .forms import SupplierForm, SupplierPaymentForm


@login_required
def supplier_list(request):
    shop = request.user.profile.shop
    suppliers = Supplier.objects.filter(shop=shop)
    query = request.GET.get("q", "").strip()
    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query) | Q(company_name__icontains=query) | Q(phone__icontains=query)
        )

    total_owed = suppliers.aggregate(Sum("balance_owed"))["balance_owed__sum"] or Decimal("0")

    paginator = Paginator(suppliers, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "purchases/supplier_list.html", {
        "suppliers": page_obj,
        "page_obj": page_obj,
        "query": query,
        "total_owed": total_owed,
    })


@login_required
def supplier_add(request):
    shop = request.user.profile.shop
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.shop = shop
            supplier.save()
            log_activity(shop, request.user, "create", "purchases", f"Supplier {supplier.name}", f"Phone: {supplier.phone}")
            messages.success(request, f"Supplier '{supplier.name}' added successfully.")
            return redirect("purchases:supplier_detail", supplier_id=supplier.id)
    else:
        form = SupplierForm()
    return render(request, "purchases/supplier_form.html", {"form": form, "title": "Add New Supplier"})


@login_required
def supplier_edit(request, supplier_id):
    shop = request.user.profile.shop
    supplier = get_object_or_404(Supplier, id=supplier_id, shop=shop)
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            log_activity(shop, request.user, "update", "purchases", f"Supplier {supplier.name}")
            messages.success(request, f"Supplier '{supplier.name}' updated successfully.")
            return redirect("purchases:supplier_detail", supplier_id=supplier.id)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, "purchases/supplier_form.html", {"form": form, "title": f"Edit {supplier.name}"})


@login_required
def supplier_detail(request, supplier_id):
    shop = request.user.profile.shop
    supplier = get_object_or_404(Supplier, id=supplier_id, shop=shop)
    purchases = supplier.purchases.all()
    payments = supplier.payments.all()
    payment_form = SupplierPaymentForm()
    return render(request, "purchases/supplier_detail.html", {
        "supplier": supplier,
        "purchases": purchases,
        "payments": payments,
        "payment_form": payment_form,
    })


@login_required
def supplier_payment_add(request, supplier_id):
    shop = request.user.profile.shop
    supplier = get_object_or_404(Supplier, id=supplier_id, shop=shop)
    if request.method == "POST":
        form = SupplierPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.supplier = supplier
            payment.save()

            # Deduct from supplier balance owed
            supplier.balance_owed = max(Decimal("0"), supplier.balance_owed - payment.amount)
            supplier.save()

            log_activity(
                shop, request.user, "payment", "purchases",
                f"Paid Rs. {payment.amount} to {supplier.name}",
                f"Mode: {payment.payment_mode}, Note: {payment.note}"
            )
            messages.success(request, f"Recorded payment of Rs. {payment.amount} to {supplier.name}.")
    return redirect("purchases:supplier_detail", supplier_id=supplier.id)


@login_required
def purchase_create(request):
    shop = request.user.profile.shop
    suppliers = Supplier.objects.filter(shop=shop)
    products = Product.objects.filter(shop=shop)

    if not suppliers.exists():
        messages.warning(request, "Please add at least one supplier before recording a purchase.")
        return redirect("purchases:supplier_add")

    if request.method == "POST":
        supplier_id = request.POST.get("supplier_id")
        supplier = get_object_or_404(Supplier, id=supplier_id, shop=shop)
        invoice_no = request.POST.get("invoice_no", "").strip()
        paid_amount = Decimal(request.POST.get("paid_amount") or 0)
        notes = request.POST.get("notes", "").strip()

        items_json = request.POST.get("items_json", "[]")
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            items = []

        if not items:
            messages.error(request, "Please add at least one product item to the purchase order.")
            return redirect("purchases:purchase_create")

        total_amount = Decimal("0")
        purchase_items_to_create = []

        for item in items:
            p_id = item.get("product_id")
            qty = int(item.get("qty", 1))
            unit_cost = Decimal(str(item.get("unit_cost", 0)))
            subtotal = unit_cost * qty
            total_amount += subtotal

            prod = get_object_or_404(Product, id=p_id, shop=shop)
            purchase_items_to_create.append((prod, qty, unit_cost, subtotal))

        # Determine payment status
        if paid_amount >= total_amount:
            payment_status = "paid"
        elif paid_amount > 0:
            payment_status = "partial"
        else:
            payment_status = "pending"

        purchase = Purchase.objects.create(
            shop=shop,
            supplier=supplier,
            invoice_no=invoice_no,
            total_amount=total_amount,
            paid_amount=paid_amount,
            payment_status=payment_status,
            notes=notes,
        )

        for prod, qty, unit_cost, subtotal in purchase_items_to_create:
            PurchaseItem.objects.create(
                purchase=purchase,
                product=prod,
                quantity=qty,
                unit_cost=unit_cost,
                subtotal=subtotal,
            )
            # Auto-increment inventory stock & update cost price
            prod.stock_qty += qty
            prod.cost_price = unit_cost
            prod.save()

        # Update supplier balance owed for unpaid portion
        unpaid = max(Decimal("0"), total_amount - paid_amount)
        if unpaid > 0:
            supplier.balance_owed += unpaid
            supplier.save()

        log_activity(
            shop, request.user, "create", "purchases",
            f"Purchase #{purchase.id} from {supplier.name}",
            f"Total: Rs. {total_amount}, Paid: Rs. {paid_amount}, Items: {len(purchase_items_to_create)}"
        )

        messages.success(request, f"Purchase order #{purchase.id} created and inventory stock updated successfully!")
        return redirect("purchases:purchase_detail", purchase_id=purchase.id)

    return render(request, "purchases/purchase_form.html", {
        "suppliers": suppliers,
        "products": products,
    })


@login_required
def purchase_list(request):
    shop = request.user.profile.shop
    purchases = Purchase.objects.filter(shop=shop)
    query = request.GET.get("q", "").strip()
    if query:
        purchases = purchases.filter(
            Q(supplier__name__icontains=query) | Q(invoice_no__icontains=query)
        )

    paginator = Paginator(purchases, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "purchases/purchase_list.html", {
        "purchases": page_obj,
        "page_obj": page_obj,
        "query": query,
    })


@login_required
def purchase_detail(request, purchase_id):
    shop = request.user.profile.shop
    purchase = get_object_or_404(Purchase, id=purchase_id, shop=shop)
    return render(request, "purchases/purchase_detail.html", {"purchase": purchase})
