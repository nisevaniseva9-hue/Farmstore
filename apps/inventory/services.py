"""
Inventory service functions.

All stock-changing operations go through here so the locking and
transaction-atomicity rules are enforced in exactly one place, rather than
being re-implemented (and potentially forgotten) in every view that
touches stock.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.catalog.models import Product

from .models import InventoryTransaction


class InsufficientStockError(Exception):
    """Raised when an operation would oversell a product."""


def get_available_stock(product):
    """Current available stock for a product: the sum of all its
    inventory transactions. No DB row lock is taken here — use
    get_available_stock_for_update() inside an atomic block when the
    result will be used to make a reservation decision."""
    total = product.inventory_transactions.aggregate(total=Sum("quantity"))["total"]
    return total if total is not None else Decimal("0")


def _get_available_stock_for_update(product_id):
    """Locks the product row (SELECT ... FOR UPDATE) and returns the
    current available stock, so concurrent callers serialize on this
    product rather than both reading a stale value and both succeeding
    when only one should."""
    # Locking the Product row itself (rather than the transaction rows,
    # which don't exist yet for a brand-new product) gives us a single,
    # simple lock per product that every stock-changing operation
    # contends on.
    Product.objects.select_for_update().get(pk=product_id)
    total = InventoryTransaction.objects.filter(product_id=product_id).aggregate(
        total=Sum("quantity")
    )["total"]
    return total if total is not None else Decimal("0")


@transaction.atomic
def add_stock(product, quantity, user=None, note=""):
    """Farmer adds new stock. Always a positive quantity."""
    if quantity <= 0:
        raise ValueError("Stock added must be a positive quantity.")

    previous_stock = get_available_stock(product)

    txn = InventoryTransaction.objects.create(
        product=product,
        transaction_type=InventoryTransaction.TransactionType.STOCK_ADDED,
        quantity=quantity,
        note=note,
        created_by=user,
    )

    if previous_stock <= 0:
        # Product just became available -- tell opted-in customers.
        # Imported lazily so the inventory app never has a hard
        # dependency on the notifications app at load time, and so a
        # WhatsApp failure can never break stock recording (send_and_record
        # already swallows its own errors, but this keeps the coupling
        # one-directional and optional).
        from apps.notifications.services import notify_customers_stock_available

        notify_customers_stock_available(product)

    return txn


@transaction.atomic
def adjust_stock(product, delta, user=None, note=""):
    """Farmer manually corrects stock (e.g. spoilage, miscount).
    `delta` may be positive or negative but not zero."""
    if delta == 0:
        raise ValueError("Adjustment quantity cannot be zero.")
    return InventoryTransaction.objects.create(
        product=product,
        transaction_type=InventoryTransaction.TransactionType.STOCK_ADJUSTMENT,
        quantity=delta,
        note=note,
        created_by=user,
    )


@transaction.atomic
def reserve_stock(product, quantity, user=None, reference=""):
    """Reserve stock for a new order. Locks the product row so that two
    simultaneous orders cannot both succeed when only enough stock exists
    for one of them. Raises InsufficientStockError if not enough stock
    is available.

    This is called from the orders app (Phase 5) when an order is created,
    inside the same atomic block as the order/order-items creation, so
    that if order creation fails the reservation rolls back too.
    """
    if quantity <= 0:
        raise ValueError("Reservation quantity must be positive.")

    available = _get_available_stock_for_update(product.pk)
    if available < quantity:
        raise InsufficientStockError(
            f"Only {available} {product.unit} of '{product.name}' available, "
            f"{quantity} requested."
        )

    return InventoryTransaction.objects.create(
        product=product,
        transaction_type=InventoryTransaction.TransactionType.ORDER_RESERVED,
        quantity=-quantity,
        reference=reference,
        created_by=user,
    )


@transaction.atomic
def cancel_reservation(product, quantity, user=None, reference=""):
    """Restores stock that was reserved for an order which is now
    rejected/cancelled before completion."""
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    return InventoryTransaction.objects.create(
        product=product,
        transaction_type=InventoryTransaction.TransactionType.ORDER_CANCELLED,
        quantity=quantity,
        reference=reference,
        created_by=user,
    )


@transaction.atomic
def complete_order(product, user=None, reference=""):
    """Purely an audit-trail marker: the stock was already deducted at
    reservation time, so this transaction carries zero quantity effect."""
    return InventoryTransaction.objects.create(
        product=product,
        transaction_type=InventoryTransaction.TransactionType.ORDER_COMPLETED,
        quantity=0,
        reference=reference,
        created_by=user,
    )
