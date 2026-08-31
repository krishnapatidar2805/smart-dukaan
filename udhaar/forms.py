from django import forms
from .models import Customer, UdhaarTransaction


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone"]


class PaymentForm(forms.Form):
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    note = forms.CharField(max_length=255, required=False)
