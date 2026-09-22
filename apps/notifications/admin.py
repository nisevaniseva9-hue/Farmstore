from django.contrib import admin

from .models import NotificationRecord


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "notification_type", "phone_number", "delivery_status",
        "related_order", "related_product", "sent_at",
    )
    list_filter = ("notification_type", "delivery_status")
    search_fields = ("phone_number", "customer__username")
    readonly_fields = [f.name for f in NotificationRecord._meta.fields]

    def has_add_permission(self, request):
        return False
