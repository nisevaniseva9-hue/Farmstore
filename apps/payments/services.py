"""
Payment service abstraction.

The order system only ever talks to a PaymentService interface -- never to
UPI or a gateway's SDK directly. That means adding Razorpay/Cashfree later
is a matter of writing a new PaymentService subclass and wiring it into
get_payment_service(); nothing in apps.orders needs to change.

Current implementation: ManualUpiPaymentService. The customer marks their
own payment as "I have paid" (which only ever moves it to
PENDING_VERIFICATION), and a farmer must manually verify it before it
becomes PAID. Customers can never mark their own payment as verified --
that authorization check lives in the views, not here, but the service
layer's method names ("submit_for_verification" vs "verify") are
deliberately distinct so it's obvious which one a customer-facing view is
allowed to call.
"""
from django.db import transaction

from apps.orders.models import Order


class PaymentServiceError(Exception):
    pass


class PaymentService:
    """Abstract interface every payment method's service must implement."""

    def submit_for_verification(self, order, reference=""):
        raise NotImplementedError

    def verify(self, order, user):
        raise NotImplementedError

    def reject(self, order, user, reason=""):
        raise NotImplementedError


class ManualUpiPaymentService(PaymentService):
    @transaction.atomic
    def submit_for_verification(self, order, reference=""):
        if order.payment_method != Order.PaymentMethod.UPI:
            raise PaymentServiceError("This order is not a UPI payment.")
        if order.payment_status != Order.PaymentStatus.PENDING:
            raise PaymentServiceError("This payment has already been submitted or resolved.")
        order.payment_status = Order.PaymentStatus.PENDING_VERIFICATION
        order.payment_reference = reference
        order.save(update_fields=["payment_status", "payment_reference", "updated_at"])
        return order

    @transaction.atomic
    def verify(self, order, user):
        """Farmer confirms the UPI payment actually arrived. Never called
        from a customer-facing view."""
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        return order

    @transaction.atomic
    def reject(self, order, user, reason=""):
        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status", "updated_at"])
        return order


class CashOnDeliveryPaymentService(PaymentService):
    """No customer-side confirmation step -- cash changes hands at
    delivery. Provided mainly so the abstraction covers both of the
    project's Phase-1 payment methods symmetrically."""

    @transaction.atomic
    def verify(self, order, user):
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        return order


_SERVICES = {
    Order.PaymentMethod.UPI: ManualUpiPaymentService,
    Order.PaymentMethod.COD: CashOnDeliveryPaymentService,
}


def get_payment_service(payment_method):
    service_class = _SERVICES.get(payment_method)
    if service_class is None:
        raise PaymentServiceError(f"No payment service registered for '{payment_method}'.")
    return service_class()
