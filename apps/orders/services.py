"""
Order creation service.

Turning a cart into an Order is the one place where inventory reservation
and order/order-item creation must succeed or fail together: if any item
can't be reserved (insufficient stock), nothing about the order should be
left behind. That's why this whole function runs inside a single
transaction.atomic() block using Django's automatic rollback-on-exception
behaviour.
"""
from decimal import Decimal

from django.db import transaction

from apps.inventory.services import (
    InsufficientStockError,
    cancel_reservation,
    complete_order,
    reserve_stock,
)

from .models import Order, OrderItem, OrderStatusHistory


class EmptyCartError(Exception):
    pass


@transaction.atomic
def create_order_from_cart(customer, cart, address, payment_method):
    """
    Creates an Order + OrderItems from the current cart contents, reserving
    inventory for each line as it goes. If any single item can't be
    reserved, the whole order (and any reservations already made for
    earlier items in this same order) is rolled back -- the customer never
    ends up with a half-placed order.
    """
    items = list(cart)
    if not items:
        raise EmptyCartError("Your cart is empty.")

    order = Order.objects.create(
        customer=customer,
        delivery_full_name=address.full_name,
        delivery_phone_number=address.phone_number,
        delivery_line1=address.line1,
        delivery_line2=address.line2,
        delivery_city=address.city,
        delivery_state=address.state,
        delivery_postal_code=address.postal_code,
        delivery_landmark=address.landmark,
        payment_method=payment_method,
        payment_status=Order.PaymentStatus.PENDING,
        status=Order.Status.PENDING,
    )

    subtotal = Decimal("0")
    for item in items:
        # Raises InsufficientStockError if not enough stock -- propagates
        # out of this function and the @transaction.atomic decorator
        # rolls back everything created so far in this call, including
        # the Order row and any earlier reservations.
        reserve_stock(
            item["product"], item["quantity"], user=customer, reference=order.order_number
        )
        order_item = OrderItem.objects.create(
            order=order,
            product=item["product"],
            product_name=item["product"].name,
            unit=item["product"].unit,
            price=item["price"],
            quantity=item["quantity"],
        )
        subtotal += order_item.total

    delivery_charge = Decimal("0")  # flat/free for now; configurable later via Settings
    order.subtotal = subtotal
    order.delivery_charge = delivery_charge
    order.total = subtotal + delivery_charge
    order.save(update_fields=["subtotal", "delivery_charge", "total"])

    OrderStatusHistory.objects.create(
        order=order, status=Order.Status.PENDING, changed_by=customer, note="Order placed by customer."
    )

    cart.clear()

    # WhatsApp notifications never block or fail order creation -- both
    # of these swallow their own errors internally (see
    # apps.notifications.services.send_and_record).
    from apps.notifications.models import NotificationRecord
    from apps.notifications.services import notify_farmer_new_order, notify_order_event

    notify_farmer_new_order(order)
    notify_order_event(order, NotificationRecord.NotificationType.ORDER_PLACED)

    return order


@transaction.atomic
def change_order_status(order, new_status, user=None, note=""):
    """The only sanctioned way for the farmer to move an order's status
    forward. Bundles the status transition with the matching inventory
    side-effect so the two can never drift apart:

    - Rejecting/cancelling an order restores the stock that was reserved
      for it (OrderCancelled transactions).
    - Marking an order delivered records an audit-trail OrderCompleted
      transaction (no stock effect -- it was already deducted at
      reservation time).
    """
    order.transition_to(new_status, user=user, note=note)

    if new_status in (Order.Status.REJECTED, Order.Status.CANCELLED):
        for item in order.items.all():
            cancel_reservation(
                item.product, item.quantity, user=user, reference=order.order_number
            )
    elif new_status == Order.Status.DELIVERED:
        for item in order.items.all():
            complete_order(item.product, user=user, reference=order.order_number)

    from apps.notifications.models import NotificationRecord
    from apps.notifications.services import notify_order_event

    _STATUS_TO_NOTIFICATION = {
        Order.Status.CONFIRMED: NotificationRecord.NotificationType.ORDER_CONFIRMED,
        Order.Status.REJECTED: NotificationRecord.NotificationType.ORDER_REJECTED,
        Order.Status.OUT_FOR_DELIVERY: NotificationRecord.NotificationType.ORDER_OUT_FOR_DELIVERY,
        Order.Status.DELIVERED: NotificationRecord.NotificationType.ORDER_DELIVERED,
    }
    notification_type = _STATUS_TO_NOTIFICATION.get(new_status)
    if notification_type:
        notify_order_event(order, notification_type)

    return order


def assign_delivery(order, delivery_date, delivery_time_slot):
    order.delivery_date = delivery_date
    order.delivery_time_slot = delivery_time_slot
    order.save(update_fields=["delivery_date", "delivery_time_slot", "updated_at"])

    from apps.notifications.models import NotificationRecord
    from apps.notifications.services import notify_order_event

    notify_order_event(order, NotificationRecord.NotificationType.DELIVERY_DATE_ASSIGNED)

    return order
