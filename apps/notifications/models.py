"""
Notifications app.

Every WhatsApp message the system attempts to send -- to a customer or to
the farmer -- gets one NotificationRecord, regardless of whether it
actually succeeded. This is the audit trail the spec asks for, and it's
also how the farmer can see delivery failures in one place.
"""
from django.conf import settings
from django.db import models


class NotificationRecord(models.Model):
    class NotificationType(models.TextChoices):
        NEW_PRODUCT_AVAILABLE = "new_product_available", "New Product Available"
        NEW_STOCK_AVAILABLE = "new_stock_available", "New Stock Available"
        ORDER_PLACED = "order_placed", "Order Placed"
        ORDER_CONFIRMED = "order_confirmed", "Order Confirmed"
        ORDER_REJECTED = "order_rejected", "Order Rejected"
        DELIVERY_DATE_ASSIGNED = "delivery_date_assigned", "Delivery Date Assigned"
        ORDER_OUT_FOR_DELIVERY = "order_out_for_delivery", "Order Out for Delivery"
        ORDER_DELIVERED = "order_delivered", "Order Delivered"
        FARMER_NEW_ORDER_ALERT = "farmer_new_order_alert", "Farmer: New Order Alert"

    class DeliveryStatus(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"
        SIMULATED = "simulated", "Simulated"

    # Nullable: farmer-alert notifications aren't tied to a customer account.
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notification_records",
    )
    phone_number = models.CharField(max_length=16)
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)

    related_order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notification_records",
    )
    related_product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notification_records",
    )

    message_template_id = models.CharField(max_length=100, blank=True)
    message_preview = models.TextField(blank=True)

    delivery_status = models.CharField(max_length=15, choices=DeliveryStatus.choices)
    error_message = models.CharField(max_length=255, blank=True)

    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["notification_type", "-sent_at"])]

    def __str__(self):
        return f"{self.get_notification_type_display()} -> {self.phone_number} ({self.delivery_status})"
