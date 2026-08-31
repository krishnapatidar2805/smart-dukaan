from django.db import models
from accounts.models import Shop
from inventory.models import Product


class Supplier(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    balance_owed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.company_name or self.phone})"


class SupplierPayment(models.Model):
    PAYMENT_MODES = (
        ("cash", "Cash"),
        ("upi", "UPI / Online"),
        ("bank", "Bank Transfer"),
        ("cheque", "Cheque"),
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default="upi")
    note = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Payment of Rs. {self.amount} to {self.supplier.name}"


class Purchase(models.Model):
    STATUS_CHOICES = (
        ("paid", "Fully Paid"),
        ("partial", "Partially Paid"),
        ("pending", "Pending (Credit)"),
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="purchases")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="purchases")
    invoice_no = models.CharField(max_length=80, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"PO #{self.id} - {self.supplier.name} (Rs. {self.total_amount})"

    @property
    def due_amount(self):
        return max(0, float(self.total_amount) - float(self.paid_amount))


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="purchase_items")
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
