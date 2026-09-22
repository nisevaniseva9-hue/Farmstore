from django import forms

from .models import PaymentSettings


class PaymentSettingsForm(forms.ModelForm):
    class Meta:
        model = PaymentSettings
        fields = ["upi_id", "upi_display_name", "qr_code_image", "farmer_whatsapp_number"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "qr_code_image":
                field.widget.attrs.setdefault("class", "form-control")


class PaymentConfirmationForm(forms.Form):
    """Customer-facing 'I Have Paid' form. Optional free-text reference
    (e.g. the last 4 digits of a UTR/transaction ID) to help the farmer
    match it up -- never trusted as proof of payment on its own."""

    reference = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Optional: UPI transaction reference",
        }),
    )


class RejectPaymentForm(forms.Form):
    reason = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
