from django.contrib import admin

from .models import PaymentSettings


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("label", "upi_id", "upi_display_name", "farmer_whatsapp_number", "updated_at")

    @admin.display(description="Settings")
    def label(self, obj):
        return "Payment & WhatsApp Settings (click to edit)"

    def has_add_permission(self, request):
        # Singleton -- block adding a second row from the admin.
        return not PaymentSettings.objects.exists()
