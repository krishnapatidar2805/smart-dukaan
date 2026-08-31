from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "cost_price", "selling_price", "stock_qty",
                  "unit", "low_stock_threshold", "expiry_date"]
        widgets = {
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }
