from django.db import models
from accounts.models import Shop


class Customer(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15)
    loyalty_points = models.IntegerField(default=0, help_text="Reward points earned by customer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def total_due(self):
        credit = self.transactions.filter(type="credit_given").aggregate(models.Sum("amount"))["amount__sum"] or 0
        paid = self.transactions.filter(type="payment_received").aggregate(models.Sum("amount"))["amount__sum"] or 0
        return float(credit) - float(paid)


class UdhaarTransaction(models.Model):
    TYPE_CHOICES = (
        ("credit_given", "Credit Given"),
        ("payment_received", "Payment Received"),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="transactions")
    bill = models.ForeignKey("billing.Bill", on_delete=models.SET_NULL, null=True, blank=True, related_name="udhaar_transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.customer.name} - {self.type} - {self.amount}"
