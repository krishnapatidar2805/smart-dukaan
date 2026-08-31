from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from accounts.utils import log_activity
from .models import Customer, UdhaarTransaction
from .forms import CustomerForm, PaymentForm


@login_required
def customer_list(request):
    shop = request.user.profile.shop
    customers = Customer.objects.filter(shop=shop)
    query = request.GET.get("q", "").strip()

    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))

    all_customers = list(customers)
    total_due = sum(c.total_due for c in all_customers)

    paginator = Paginator(all_customers, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "udhaar/customer_list.html", {
        "customers": page_obj,
        "page_obj": page_obj,
        "total_due": total_due,
        "query": query,
    })


@login_required
def customer_add(request):
    shop = request.user.profile.shop
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.shop = shop
            customer.save()
            log_activity(shop, request.user, "create", "udhaar", f"Customer {customer.name}", f"Phone: {customer.phone}")
            messages.success(request, f"Customer '{customer.name}' added successfully.")
            return redirect("udhaar:customer_detail", pk=customer.id)
    else:
        form = CustomerForm()
    return render(request, "udhaar/customer_form.html", {"form": form})


@login_required
def customer_detail(request, pk):
    shop = request.user.profile.shop
    customer = get_object_or_404(Customer, pk=pk, shop=shop)
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            note = form.cleaned_data.get("note", "")
            tx = UdhaarTransaction.objects.create(
                customer=customer, amount=amount,
                type="payment_received", note=note,
            )
            log_activity(
                shop, request.user, "payment", "udhaar",
                f"Customer Payment from {customer.name}",
                f"Received Rs. {amount}. Note: {note}"
            )
            messages.success(request, f"Payment of Rs. {amount} recorded successfully.")
            return redirect("udhaar:customer_detail", pk=pk)
    else:
        form = PaymentForm()
    transactions = customer.transactions.all()
    return render(request, "udhaar/customer_detail.html", {
        "customer": customer, "transactions": transactions, "form": form,
    })
