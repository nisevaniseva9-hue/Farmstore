"""
Payments app.

PaymentSettings is a farmer-configured singleton holding the UPI ID,
display name, and QR code image shown to customers at checkout. Actual
payment gateway credentials/secrets (Phase 9+ if a real gateway is ever
added) belong in environment variables, never in this table -- this model
only holds the farmer's own public UPI handle, which is meant to be shown
to customers.
"""
from django.db import models


def qr_code_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"payment_settings/upi_qr.{ext}"


class PaymentSettings(models.Model):
    upi_id = models.CharField(
        max_length=100, blank=True, help_text="e.g. farmer@upi"
    )
    upi_display_name = models.CharField(max_length=100, blank=True)
    qr_code_image = models.ImageField(
        upload_to=qr_code_upload_path, blank=True, null=True
    )
    farmer_whatsapp_number = models.CharField(
        max_length=16, blank=True,
        help_text="Where new-order WhatsApp alerts are sent (Phase 8).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Payment settings"

    def __str__(self):
        return "Payment Settings"

    def save(self, *args, **kwargs):
        # Enforce a singleton row -- there is exactly one farm-wide UPI
        # configuration, not one per something.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_configured(self):
        return bool(self.upi_id)
