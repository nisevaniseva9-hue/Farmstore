from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from apps.orders.models import Order

from .forms import PaymentConfirmationForm, PaymentSettingsForm, RejectPaymentForm
from .models import PaymentSettings
from .services import PaymentServiceError, get_payment_service


def _is_farmer(user):
    return user.is_authenticated and user.is_farmer


farmer_required = user_passes_test(_is_farmer, login_url="accounts:login")


# ---------------------------------------------------------------------------
# Customer-facing: Scan & Pay / "I Have Paid"
# ---------------------------------------------------------------------------

@login_required
def pay_upi(request, order_number):
    # Ownership check baked into the lookup: a customer can never load
    # another customer's payment screen, not even by guessing the order
    # number.
    order = get_object_or_404(
        Order, order_number=order_number, customer=request.user,
        payment_method=Order.PaymentMethod.UPI,
    )
    settings_obj = PaymentSettings.get_settings()

    if order.payment_status != Order.PaymentStatus.PENDING:
        # Already submitted/verified/failed -- nothing to do here, just
        # show them the order.
        return redirect("orders:order_detail", order_number=order.order_number)

    if request.method == "POST":
        form = PaymentConfirmationForm(request.POST)
        if form.is_valid():
            service = get_payment_service(Order.PaymentMethod.UPI)
            try:
                service.submit_for_verification(order, reference=form.cleaned_data["reference"])
            except PaymentServiceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Thanks! We've marked your payment as submitted. "
                    "The farmer will verify it shortly.",
                )
                return redirect("orders:order_detail", order_number=order.order_number)
    else:
        form = PaymentConfirmationForm()

    return render(
        request, "payments/pay_upi.html",
        {"order": order, "settings": settings_obj, "form": form},
    )


# ---------------------------------------------------------------------------
# Farmer-only: settings + manual verification
# ---------------------------------------------------------------------------

@farmer_required
def payment_settings(request):
    settings_obj = PaymentSettings.get_settings()
    if request.method == "POST":
        form = PaymentSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Payment settings updated.")
            return redirect("farmer_payments:payment_settings")
    else:
        form = PaymentSettingsForm(instance=settings_obj)
    return render(request, "farmer/payments/settings.html", {"form": form, "settings": settings_obj})


@farmer_required
def pending_verifications(request):
    orders = Order.objects.filter(
        payment_method=Order.PaymentMethod.UPI,
        payment_status=Order.PaymentStatus.PENDING_VERIFICATION,
    ).select_related("customer")
    return render(request, "farmer/payments/pending_list.html", {"orders": orders})


@farmer_required
def verify_payment(request, order_number):
    # Customers must never be able to reach this: it's farmer_required,
    # and it only ever moves PENDING_VERIFICATION -> PAID/FAILED, never
    # sets PAID directly from a customer action anywhere in the codebase.
    order = get_object_or_404(
        Order, order_number=order_number,
        payment_method=Order.PaymentMethod.UPI,
        payment_status=Order.PaymentStatus.PENDING_VERIFICATION,
    )
    service = get_payment_service(Order.PaymentMethod.UPI)

    if request.method == "POST":
        if "approve" in request.POST:
            service.verify(order, user=request.user)
            messages.success(request, f"Payment for {order.order_number} marked as Paid.")
        elif "reject" in request.POST:
            form = RejectPaymentForm(request.POST)
            reason = form.data.get("reason", "")
            service.reject(order, user=request.user, reason=reason)
            messages.warning(request, f"Payment for {order.order_number} marked as Failed.")
        return redirect("farmer_payments:pending_verifications")

    return render(request, "farmer/payments/verify.html", {"order": order})
