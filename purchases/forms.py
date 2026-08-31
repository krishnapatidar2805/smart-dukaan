from django import forms
from .models import Supplier, Purchase, SupplierPayment


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "company_name", "phone", "email", "address", "balance_owed"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Ramesh Kumar"}),
            "company_name": forms.TextInput(attrs={"placeholder": "e.g. Balaji Traders & Distributors"}),
            "phone": forms.TextInput(attrs={"placeholder": "e.g. 9876543210"}),
            "email": forms.EmailInput(attrs={"placeholder": "supplier@example.com (optional)"}),
            "address": forms.Textarea(attrs={"rows": 2, "placeholder": "City / Market address"}),
            "balance_owed": forms.NumberInput(attrs={"placeholder": "0.00 (Initial balance if any)"}),
        }


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ["amount", "payment_mode", "note"]
        widgets = {
            "amount": forms.NumberInput(attrs={"placeholder": "Enter paid amount", "min": "1"}),
            "note": forms.TextInput(attrs={"placeholder": "e.g. GPay ref / Cash receipt"}),
        }
