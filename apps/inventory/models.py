"""
Inventory app.

Stock is never stored as a single mutable number on Product. Instead every
change is recorded as an InventoryTransaction, and available stock is the
running sum of those transactions. This gives a full audit trail and lets
us prevent overselling by locking rows during order placement (see
services.py).
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalog.models import Product


class InventoryTransaction(models.Model):
    class TransactionType(models.TextChoices):
        STOCK_ADDED = "stock_added", "Stock Added"
        STOCK_ADJUSTMENT = "stock_adjustment", "Stock Adjustment"
        ORDER_RESERVED = "order_reserved", "Order Reserved"
        ORDER_CANCELLED = "order_cancelled", "Order Cancelled"
        ORDER_COMPLETED = "order_completed", "Order Completed"

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Signed amount. Positive increases available stock, negative decreases it.",
    )
    note = models.CharField(max_length=255, blank=True)
    reference = models.CharField(
        max_length=50, blank=True,
        help_text="Optional external reference, e.g. an order number (orders app added in Phase 5).",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["product", "-created_at"])]

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.quantity} - {self.product.name}"
