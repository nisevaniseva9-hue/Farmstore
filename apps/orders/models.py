"""
Orders app: Order, OrderItem, OrderStatusHistory.

Key rules enforced here (from the project spec):
- OrderItem snapshots product name/price/unit at order time. Future price
  changes on the Product must never alter historical orders.
- Order status changes go through a controlled transition map, and every
  change is recorded in OrderStatusHistory.
- Delivery address details are snapshotted onto the Order itself (not just
  a FK to Address), so editing/deleting an address later never rewrites
  order history.
"""
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalog.models import Product


def generate_order_number():
    return f"FARM-{uuid.uuid4().hex[:8].upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        PREPARING = "preparing", "Preparing"
        DELIVERY_SCHEDULED = "delivery_scheduled", "Delivery Scheduled"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    # Which status can move to which. Enforced by transition_to().
    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.REJECTED, Status.CANCELLED},
        Status.CONFIRMED: {Status.PREPARING, Status.CANCELLED},
        Status.PREPARING: {Status.DELIVERY_SCHEDULED, Status.CANCELLED},
        Status.DELIVERY_SCHEDULED: {Status.OUT_FOR_DELIVERY, Status.CANCELLED},
        Status.OUT_FOR_DELIVERY: {Status.DELIVERED},
        Status.DELIVERED: set(),
        Status.REJECTED: set(),
        Status.CANCELLED: set(),
    }

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        UPI = "upi", "UPI"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PENDING_VERIFICATION = "pending_verification", "Payment Pending Verification"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    order_number = models.CharField(
        max_length=20, unique=True, editable=False, default=generate_order_number
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )

    # Delivery address -- snapshotted at order time (see module docstring).
    delivery_full_name = models.CharField(max_length=150)
    delivery_phone_number = models.CharField(max_length=16)
    delivery_line1 = models.CharField(max_length=255)
    delivery_line2 = models.CharField(max_length=255, blank=True)
    delivery_city = models.CharField(max_length=100)
    delivery_state = models.CharField(max_length=100)
    delivery_postal_code = models.CharField(max_length=12)
    delivery_landmark = models.CharField(max_length=255, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        max_length=25, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    payment_reference = models.CharField(
        max_length=100, blank=True,
        help_text="Customer-entered UPI transaction reference, if any (Phase 7).",
    )

    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.PENDING
    )

    delivery_date = models.DateField(null=True, blank=True)
    delivery_time_slot = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status, user=None, note=""):
        """The only sanctioned way to change an order's status. Raises
        ValueError on an illegal transition, and always logs the change."""
        if new_status == self.status:
            raise ValueError(f"Order is already in status '{self.status}'.")
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Cannot move order from '{self.status}' to '{new_status}'."
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        OrderStatusHistory.objects.create(
            order=self, status=new_status, changed_by=user, note=note
        )


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")

    # Snapshots -- deliberately duplicated from Product so later edits to
    # the product never change what a historical order shows.
    product_name = models.CharField(max_length=150)
    unit = models.CharField(max_length=10)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(0.01)]
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} x {self.product_name} ({self.order.order_number})"

    @property
    def total(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        if not self.product_name:
            self.product_name = self.product.name
        if not self.unit:
            self.unit = self.product.unit
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="status_history"
    )
    status = models.CharField(max_length=25, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "Order status history"

    def __str__(self):
        return f"{self.order.order_number}: {self.status}"
