from django.db import models
from accounts.models import Shop


class Product(models.Model):
    UNIT_CHOICES = (
        ("pcs", "Pieces"),
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("l", "Litre"),
        ("ml", "Millilitre"),
        ("box", "Box"),
        ("packet", "Packet"),
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=80, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_qty = models.IntegerField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="pcs")
    low_stock_threshold = models.IntegerField(default=10)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock_qty <= self.low_stock_threshold

    @property
    def profit_margin(self):
        if self.selling_price and self.cost_price is not None:
            return round(float(self.selling_price) - float(self.cost_price), 2)
        return 0
