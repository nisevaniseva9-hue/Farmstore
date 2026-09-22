from decimal import Decimal

from django import forms

from apps.accounts.models import Address

from .models import Order


class CartAddForm(forms.Form):
    quantity = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )


class AddressChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, address):
        label = address.label or "Address"
        default = " (default)" if address.is_default else ""
        return f"{label}{default}: {address.full_name}, {address.line1}, {address.city}"


class CheckoutForm(forms.Form):
    address = AddressChoiceField(queryset=Address.objects.none(), empty_label=None)
    payment_method = forms.ChoiceField(
        choices=Order.PaymentMethod.choices,
        widget=forms.RadioSelect,
        initial=Order.PaymentMethod.COD,
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["address"].queryset = Address.objects.filter(customer=user)
        self.fields["address"].widget.attrs.setdefault("class", "form-control")


class OrderStatusChangeForm(forms.Form):
    status = forms.ChoiceField(choices=[])
    note = forms.CharField(max_length=255, required=False, widget=forms.TextInput())

    def __init__(self, *args, **kwargs):
        order = kwargs.pop("order")
        super().__init__(*args, **kwargs)
        allowed = Order.ALLOWED_TRANSITIONS.get(order.status, set())
        self.fields["status"].choices = [
            (choice.value, choice.label) for choice in Order.Status if choice in allowed
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class DeliveryAssignmentForm(forms.Form):
    delivery_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    delivery_time_slot = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            "class": "form-control", "placeholder": "e.g. 10:00 AM - 1:00 PM"
        }),
    )
