from django.db import models
from django.contrib.auth.models import User


class Shop(models.Model):
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_shops")
    upi_id = models.CharField(max_length=100, blank=True, default="shopkeeper@upi", help_text="UPI ID for on-screen QR Code payments")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Profile(models.Model):
    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("staff", "Staff"),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="staff_members", null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="owner")
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ("create", "Created"),
        ("update", "Updated"),
        ("delete", "Deleted"),
        ("return", "Refund / Return"),
        ("payment", "Payment / Settlement"),
        ("cash_register", "Cash Register"),
        ("export", "Data Export"),
    )
    MODULE_CHOICES = (
        ("inventory", "Inventory"),
        ("billing", "Billing & POS"),
        ("purchases", "Purchases & Suppliers"),
        ("udhaar", "Udhaar Ledger"),
        ("cash_register", "Cash Register"),
        ("accounts", "Accounts & Staff"),
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="audit_logs")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    object_repr = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.timestamp.strftime('%d-%m-%Y %H:%M')}] {self.user} - {self.action} on {self.object_repr}"
