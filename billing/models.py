from django.db import models
from accounts.models import Shop
from inventory.models import Product
from udhaar.models import Customer


class Bill(models.Model):
    PAYMENT_CHOICES = (
        ("cash", "Cash"),
        ("upi", "UPI"),
        ("card", "Card"),
        ("udhaar", "Udhaar (Credit)"),
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="bills")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="bills")
    customer_name_snapshot = models.CharField(max_length=120, blank=True)
    customer_phone_snapshot = models.CharField(max_length=15, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="cash")
    points_earned = models.IntegerField(default=0, help_text="Loyalty reward points earned on this bill")
    points_redeemed = models.IntegerField(default=0, help_text="Loyalty points redeemed as discount")
    whatsapp_sent = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Bill #{self.id} - {self.date.strftime('%d-%m-%Y')}"

    @property
    def gst_amount(self):
        return round(float(self.subtotal) * (float(self.gst_percent) / 100), 2)


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name_snapshot = models.CharField(max_length=150)
    quantity = models.IntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return round(float(self.quantity) * float(self.price_at_sale), 2)


class BillReturn(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="returns")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="bill_returns")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    return_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-return_date"]

    def __str__(self):
        return f"Return for Bill #{self.bill.id} - Rs. {self.refund_amount}"


class BillReturnItem(models.Model):
    return_record = models.ForeignKey(BillReturn, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField()
    refund_rate = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Returned {self.quantity} x {self.product.name if self.product else 'Product'}"


class CashRegister(models.Model):
    STATUS_CHOICES = (
        ("open", "Open"),
        ("closed", "Closed"),
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="cash_registers")
    date = models.DateField()
    opening_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_in = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_out = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expected_closing = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_closing = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discrepancy = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    opened_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, related_name="opened_registers")
    closed_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_registers")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-opened_at"]

    def __str__(self):
        return f"Register {self.date} ({self.status}) - Shop: {self.shop.name}"
