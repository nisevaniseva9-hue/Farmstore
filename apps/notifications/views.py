import urllib.parse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render

from apps.orders.models import Order
from .models import NotificationRecord
from .services import (
    WhatsAppNotificationService,
    format_delivery_assigned_message,
    format_order_approved_message,
    format_order_placed_message,
    normalize_phone_number,
    send_and_record,
)


def _is_farmer(user):
    return user.is_authenticated and user.is_farmer


farmer_required = user_passes_test(_is_farmer, login_url="accounts:login")


@farmer_required
def notification_list(request):
    notifications = NotificationRecord.objects.select_related(
        "customer", "related_order", "related_product"
    )[:200]
    return render(request, "farmer/notifications/list.html", {"notifications": notifications})


@farmer_required
def notification_test(request):
    provider = getattr(settings, "WHATSAPP_PROVIDER", "console")
    is_configured = WhatsAppNotificationService().is_configured()

    sample_order = Order.objects.order_by("-created_at").first()

    preview_message = ""
    target_phone = ""
    wa_me_url = ""

    if sample_order:
        preview_message = format_order_placed_message(sample_order)
    else:
        farm_name = getattr(settings, "FARM_NAME", "Farm Fresh")
        preview_message = (
            f"🌱 *{farm_name}* — *Order Placed!* 🛍️\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 *Order Number*: FARM-DEMO123\n"
            f"👤 *Recipient*: Demo Customer\n"
            f"📅 *Date*: Today\n\n"
            f"📦 *Products Ordered*:\n"
            f"  • *Fresh Farm Tomato*: 2 kg × ₹40.00 = *₹80.00*\n"
            f"  • *Organic Spinach*: 1 bunch × ₹30.00 = *₹30.00*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 *Subtotal*: ₹110.00\n"
            f"🚚 *Delivery Charge*: ₹0.00\n"
            f"💰 *Total Amount*: *₹110.00*\n"
            f"💳 *Payment*: Cash on Delivery (Pending)\n\n"
            f"📍 *Deliver To*:\nFlat 402, Green Meadows, Pune, MH - 411001\n\n"
            f"🌾 We are reviewing your order. You will receive an update once it is approved and scheduled for delivery!"
        )

    if request.method == "POST":
        msg_type = request.POST.get("msg_type", "order_placed")
        target_phone = request.POST.get("phone", "").strip()
        custom_text = request.POST.get("custom_text", "").strip()

        if custom_text:
            text_to_send = custom_text
        elif msg_type == "order_approved" and sample_order:
            text_to_send = format_order_approved_message(sample_order)
        elif msg_type == "delivery_scheduled" and sample_order:
            text_to_send = format_delivery_assigned_message(sample_order)
        elif sample_order:
            text_to_send = format_order_placed_message(sample_order)
        else:
            text_to_send = preview_message

        preview_message = text_to_send

        if "send_simulated" in request.POST:
            record = send_and_record(
                customer=request.user,
                phone_number=target_phone or "919999999999",
                notification_type=NotificationRecord.NotificationType.ORDER_PLACED,
                message=text_to_send,
                related_order=sample_order,
                template_id="test_simulator",
            )
            messages.success(
                request,
                f"Test notification logged! Delivery Status: {record.get_delivery_status_display()} (Preview saved in database and logged to server console)."
            )
            return redirect("farmer_notifications:notification_list")

        clean_phone = normalize_phone_number(target_phone).lstrip("+")
        if clean_phone:
            wa_me_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(text_to_send)}"

    context = {
        "provider": provider,
        "is_configured": is_configured,
        "sample_order": sample_order,
        "preview_message": preview_message,
        "target_phone": target_phone,
        "wa_me_url": wa_me_url,
    }
    return render(request, "farmer/notifications/test.html", context)

