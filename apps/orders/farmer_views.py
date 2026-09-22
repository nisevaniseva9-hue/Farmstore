"""
Farmer-only order management: dashboard, order list/detail with status
transitions, delivery scheduling, and a simple customer list.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product
from apps.inventory.views import LOW_STOCK_THRESHOLD
from apps.inventory.services import get_available_stock

from .forms import DeliveryAssignmentForm, OrderStatusChangeForm
from .models import Order
from .services import assign_delivery, change_order_status

User = get_user_model()


def _is_farmer(user):
    return user.is_authenticated and user.is_farmer


farmer_required = user_passes_test(_is_farmer, login_url="accounts:login")


@farmer_required
def dashboard(request):
    products = Product.objects.all()
    total_products = products.count()

    in_stock_count = 0
    low_stock_count = 0
    for product in products:
        stock = get_available_stock(product)
        if stock > 0:
            in_stock_count += 1
        if 0 < stock <= LOW_STOCK_THRESHOLD:
            low_stock_count += 1

    pending_orders = Order.objects.filter(status=Order.Status.PENDING).count()
    todays_orders = Order.objects.filter(created_at__date=date.today()).count()

    total_sales = Order.objects.exclude(
        status__in=[Order.Status.REJECTED, Order.Status.CANCELLED]
    ).aggregate(total=Sum("total"))["total"] or 0

    recent_orders = Order.objects.select_related("customer").all()[:10]

    context = {
        "total_products": total_products,
        "in_stock_count": in_stock_count,
        "low_stock_count": low_stock_count,
        "pending_orders": pending_orders,
        "todays_orders": todays_orders,
        "total_sales": total_sales,
        "recent_orders": recent_orders,
    }
    return render(request, "farmer/dashboard.html", context)


STATUS_TABS = [
    ("pending", "Pending"),
    ("confirmed", "Confirmed"),
    ("preparing", "Preparing"),
    ("delivery_scheduled", "Delivery Scheduled"),
    ("out_for_delivery", "Out for Delivery"),
    ("delivered", "Delivered"),
    ("cancelled", "Cancelled"),
    ("rejected", "Rejected"),
]


@farmer_required
def order_list(request):
    status = request.GET.get("status", "pending")
    orders = Order.objects.select_related("customer").all()
    if status != "all":
        orders = orders.filter(status=status)
    return render(
        request, "farmer/orders/order_list.html",
        {"orders": orders, "status_tabs": STATUS_TABS, "current_status": status},
    )


@farmer_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)

    status_form = OrderStatusChangeForm(order=order)
    delivery_form = DeliveryAssignmentForm(
        initial={"delivery_date": order.delivery_date, "delivery_time_slot": order.delivery_time_slot}
    )

    if request.method == "POST":
        if "change_status" in request.POST:
            status_form = OrderStatusChangeForm(request.POST, order=order)
            if status_form.is_valid():
                try:
                    change_order_status(
                        order,
                        status_form.cleaned_data["status"],
                        user=request.user,
                        note=status_form.cleaned_data["note"],
                    )
                    messages.success(request, "Order status updated.")
                    return redirect("farmer_orders:order_detail", order_number=order.order_number)
                except ValueError as exc:
                    messages.error(request, str(exc))
        elif "assign_delivery" in request.POST:
            delivery_form = DeliveryAssignmentForm(request.POST)
            if delivery_form.is_valid():
                assign_delivery(
                    order,
                    delivery_form.cleaned_data["delivery_date"],
                    delivery_form.cleaned_data["delivery_time_slot"],
                )
                messages.success(request, "Delivery schedule updated.")
                return redirect("farmer_orders:order_detail", order_number=order.order_number)

        elif "send_whatsapp" in request.POST:
            from apps.notifications.services import (
                notify_order_event,
                send_manual_order_notification,
            )
            from apps.notifications.models import NotificationRecord

            custom_msg = request.POST.get("custom_message", "").strip()
            if custom_msg:
                record = send_manual_order_notification(order, custom_msg)
                messages.success(request, f"WhatsApp message sent to {record.phone_number} (status: {record.get_delivery_status_display()}).")
            else:
                target_type = (
                    NotificationRecord.NotificationType.ORDER_CONFIRMED
                    if order.status == Order.Status.CONFIRMED
                    else NotificationRecord.NotificationType.ORDER_PLACED
                )
                record = notify_order_event(order, target_type)
                if record:
                    messages.success(request, f"WhatsApp notification sent to {record.phone_number} (status: {record.get_delivery_status_display()}).")
                else:
                    messages.warning(request, "Could not send notification (no valid phone number found).")
            return redirect("farmer_orders:order_detail", order_number=order.order_number)

    import urllib.parse
    from apps.notifications.services import normalize_phone_number

    raw_phone = order.delivery_phone_number
    try:
        if order.customer.customer_profile.whatsapp_number:
            raw_phone = order.customer.customer_profile.whatsapp_number
    except Exception:
        pass
    clean_phone = normalize_phone_number(raw_phone).lstrip("+")
    chat_prefill = urllib.parse.quote(f"Hi {order.delivery_full_name}, regarding your order {order.order_number} from Farm Fresh:")
    wa_me_url = f"https://wa.me/{clean_phone}?text={chat_prefill}" if clean_phone else ""

    latest_notification = order.notification_records.first()

    return render(
        request,
        "farmer/orders/order_detail.html",
        {
            "order": order,
            "status_form": status_form,
            "delivery_form": delivery_form,
            "wa_me_url": wa_me_url,
            "latest_notification": latest_notification,
        },
    )


@farmer_required
def customer_list(request):
    customers = User.objects.filter(role=User.Role.CUSTOMER).annotate(
        order_count=Count("orders")
    )
    return render(request, "farmer/customers/customer_list.html", {"customers": customers})
