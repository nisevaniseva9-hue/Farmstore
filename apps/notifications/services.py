"""
WhatsAppNotificationService.

This is the ONLY place in the codebase that knows how to actually talk to
the WhatsApp Business Cloud API. Every other app (inventory, orders,
payments) calls the small set of functions at the bottom of this file
(notify_customers_stock_available, notify_order_event,
notify_farmer_new_order, ...) and never touches the API or credentials
directly. If WhatsApp integration ever needs to change providers, this is
the only file that should need editing.

A failed or skipped WhatsApp send NEVER raises out to the caller -- the
business action that triggered it (adding stock, placing an order) must
always succeed regardless of whether the notification could be sent.
Every attempt is recorded in NotificationRecord either way.
"""
import logging
import re
import uuid

from django.conf import settings

from .models import NotificationRecord

logger = logging.getLogger(__name__)


def normalize_phone_number(raw_phone):
    """Normalizes phone numbers to E.164 international format (+<country><number>).
    Defaults to India (+91) if a 10-digit number without country code is provided."""
    if not raw_phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", str(raw_phone).strip())
    if not cleaned:
        return ""
    if cleaned.startswith("+"):
        return cleaned
    if len(cleaned) == 10:
        return f"+91{cleaned}"
    if len(cleaned) == 12 and cleaned.startswith("91"):
        return f"+{cleaned}"
    return f"+{cleaned}"


class WhatsAppNotificationService:
    """Wraps the WhatsApp Business API / Twilio / Console. Isolated in its own class
    so it is swappable and tests can substitute a fake without touching business logic."""

    def is_configured(self):
        provider = getattr(settings, "WHATSAPP_PROVIDER", "meta").lower()
        if provider == "console":
            return True
        if provider == "twilio":
            return bool(
                getattr(settings, "TWILIO_ACCOUNT_SID", None)
                and getattr(settings, "TWILIO_AUTH_TOKEN", None)
                and getattr(settings, "TWILIO_WHATSAPP_FROM", None)
            )
        return bool(
            getattr(settings, "WHATSAPP_API_TOKEN", None)
            and getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
        )

    def send_message(self, phone_number, message):
        """Sends one WhatsApp message through the configured provider."""
        provider = getattr(settings, "WHATSAPP_PROVIDER", "meta").lower()

        if provider == "console":
            logger.info(
                "\n================ [SIMULATED WHATSAPP MESSAGE] ================\n"
                "To: %s\n"
                "Content:\n%s\n"
                "==============================================================",
                phone_number,
                message,
            )
            return {"status": "simulated", "id": f"sim_{uuid.uuid4().hex[:12]}"}

        if provider == "twilio":
            if not self.is_configured():
                raise WhatsAppNotConfiguredError(
                    "Twilio WhatsApp credentials are not configured (set "
                    "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM)."
                )
            return self._call_twilio_api(phone_number, message)

        if not self.is_configured():
            raise WhatsAppNotConfiguredError(
                "WhatsApp API credentials are not configured (set "
                "WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID)."
            )
        return self._call_api(phone_number, message)

    def _call_api(self, phone_number, message):
        """The actual network call to Meta's Graph API. Kept as its own
        method so it's the single point tests monkeypatch/mock -- nothing
        else here needs to change to run fully offline in tests."""
        import requests

        clean_number = normalize_phone_number(phone_number).lstrip("+")
        url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "text",
            "text": {"body": message},
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def _call_twilio_api(self, phone_number, message):
        """Twilio WhatsApp REST API call."""
        import requests
        from requests.auth import HTTPBasicAuth

        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        from_number = settings.TWILIO_WHATSAPP_FROM

        clean_number = normalize_phone_number(phone_number)
        to_number = (
            clean_number if clean_number.startswith("whatsapp:") else f"whatsapp:{clean_number}"
        )

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = {
            "From": from_number,
            "To": to_number,
            "Body": message,
        }
        response = requests.post(
            url, data=data, auth=HTTPBasicAuth(account_sid, auth_token), timeout=10
        )
        response.raise_for_status()
        return response.json()


class WhatsAppNotConfiguredError(Exception):
    pass


def send_and_record(
    *, customer, phone_number, notification_type, message,
    related_order=None, related_product=None, template_id="",
):
    """Send one WhatsApp message and record the outcome, no matter what
    happens. This is the function every other app should call -- never
    WhatsAppNotificationService directly."""
    normalized_phone = normalize_phone_number(phone_number)
    if not normalized_phone:
        return NotificationRecord.objects.create(
            customer=customer, phone_number="", notification_type=notification_type,
            related_order=related_order, related_product=related_product,
            message_template_id=template_id, message_preview=message[:500],
            delivery_status=NotificationRecord.DeliveryStatus.SKIPPED,
            error_message="No phone number on file.",
        )

    service = WhatsAppNotificationService()
    try:
        res = service.send_message(normalized_phone, message)
    except WhatsAppNotConfiguredError as exc:
        status = NotificationRecord.DeliveryStatus.SKIPPED
        error = str(exc)
        logger.info("WhatsApp notification skipped (not configured): %s", error)
    except Exception as exc:  # noqa: BLE001
        status = NotificationRecord.DeliveryStatus.FAILED
        error = str(exc)
        logger.warning("WhatsApp notification failed: %s", error)
    else:
        if isinstance(res, dict) and res.get("status") == "simulated":
            status = NotificationRecord.DeliveryStatus.SIMULATED
        else:
            status = NotificationRecord.DeliveryStatus.SENT
        error = ""

    return NotificationRecord.objects.create(
        customer=customer, phone_number=phone_number, notification_type=notification_type,
        related_order=related_order, related_product=related_product,
        message_template_id=template_id, message_preview=message[:1000],
        delivery_status=status, error_message=error,
    )


# ---------------------------------------------------------------------------
# Rich Message Formatters
# ---------------------------------------------------------------------------

def format_order_placed_message(order):
    """Builds an itemized order confirmation WhatsApp message with full product details."""
    farm_name = getattr(settings, "FARM_NAME", "Farm Fresh")
    items = order.items.all()
    item_lines = []
    for item in items:
        item_lines.append(
            f"  • *{item.product_name}*: {item.quantity} {item.unit} × ₹{item.price} = *₹{item.total}*"
        )
    items_text = "\n".join(item_lines) if item_lines else "  • (Order items)"

    address_parts = [
        order.delivery_full_name,
        order.delivery_line1,
        order.delivery_line2,
        f"{order.delivery_city}, {order.delivery_state} - {order.delivery_postal_code}",
    ]
    address_text = ", ".join(p for p in address_parts if p)

    date_str = order.created_at.strftime("%d %b %Y, %I:%M %p") if order.created_at else "Today"

    return (
        f"🌱 *{farm_name}* — *Order Placed!* 🛍️\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Order Number*: {order.order_number}\n"
        f"👤 *Recipient*: {order.delivery_full_name}\n"
        f"📅 *Date*: {date_str}\n\n"
        f"📦 *Products Ordered*:\n"
        f"{items_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Subtotal*: ₹{order.subtotal}\n"
        f"🚚 *Delivery Charge*: ₹{order.delivery_charge}\n"
        f"💰 *Total Amount*: *₹{order.total}*\n"
        f"💳 *Payment*: {order.get_payment_method_display()} ({order.get_payment_status_display()})\n\n"
        f"📍 *Deliver To*:\n{address_text}\n\n"
        f"🌾 We are reviewing your order. You will receive an update once it is approved and scheduled for delivery!"
    )


def format_order_approved_message(order):
    """Builds an approval and delivery update message sent when farmer confirms order."""
    farm_name = getattr(settings, "FARM_NAME", "Farm Fresh")
    delivery_info = ""
    if order.delivery_date:
        slot = f" ({order.delivery_time_slot})" if order.delivery_time_slot else ""
        delivery_info = f"\n📅 *Scheduled Delivery*: *{order.delivery_date.strftime('%d %b %Y')}*{slot}"

    return (
        f"✅ *{farm_name}* — *Order Approved & Confirmed!* 🚜\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Order Number*: {order.order_number}\n"
        f"🎉 Great news! Your order has been approved by the farm and is being packed fresh."
        f"{delivery_info}\n\n"
        f"💰 *Total Payable*: ₹{order.total} ({order.get_payment_method_display()})\n"
        f"📍 *Delivery Destination*: {order.delivery_full_name}, {order.delivery_city}\n\n"
        f"🌱 Thank you for choosing organic, locally harvested farm produce!"
    )


def format_delivery_assigned_message(order):
    """Builds a message notifying customer of an assigned delivery date and time slot."""
    farm_name = getattr(settings, "FARM_NAME", "Farm Fresh")
    slot = f" ({order.delivery_time_slot})" if order.delivery_time_slot else ""
    date_display = order.delivery_date.strftime("%d %b %Y") if order.delivery_date else "Scheduled"
    return (
        f"🚚 *{farm_name}* — *Delivery Scheduled!* 📦\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Order Number*: {order.order_number}\n"
        f"📅 *Delivery Date*: *{date_display}*{slot}\n"
        f"📍 *Address*: {order.delivery_line1}, {order.delivery_city}\n\n"
        f"Your fresh package will arrive during this delivery window. Thank you for your patience!"
    )


# ---------------------------------------------------------------------------
# Business-level entry points -- what other apps actually call.
# ---------------------------------------------------------------------------

def _opted_in_customers():
    from apps.accounts.models import CustomerProfile

    return CustomerProfile.objects.filter(
        whatsapp_notifications_enabled=True
    ).exclude(whatsapp_number="").select_related("user")


def notify_customers_stock_available(product):
    """Called when a product goes from zero/no stock to available (or
    triggered manually by the farmer). Notifies every opted-in customer."""
    farm_name = getattr(settings, "FARM_NAME", "Farm Fresh")
    message = (
        f"🌱 *{farm_name}*: *{product.name}* is now available! "
        f"₹{product.price} / {product.get_unit_display()}. Order now on our website."
    )
    records = []
    for profile in _opted_in_customers():
        records.append(send_and_record(
            customer=profile.user,
            phone_number=profile.whatsapp_number,
            notification_type=NotificationRecord.NotificationType.NEW_STOCK_AVAILABLE,
            message=message,
            related_product=product,
            template_id="stock_available",
        ))
    return records


def notify_new_product_available(product):
    farm_name = getattr(settings, "FARM_NAME", "Farm Fresh")
    message = (
        f"✨ *{farm_name} New Arrival*: *{product.name}*! ₹{product.price} / {product.get_unit_display()}. "
        f"Check it out on our website."
    )
    records = []
    for profile in _opted_in_customers():
        records.append(send_and_record(
            customer=profile.user,
            phone_number=profile.whatsapp_number,
            notification_type=NotificationRecord.NotificationType.NEW_PRODUCT_AVAILABLE,
            message=message,
            related_product=product,
            template_id="new_product",
        ))
    return records


_ORDER_EVENT_MESSAGES = {
    NotificationRecord.NotificationType.ORDER_PLACED:
        "Your order {order} has been placed! We'll notify you once it's confirmed.",
    NotificationRecord.NotificationType.ORDER_CONFIRMED:
        "Good news! Your order {order} has been confirmed.",
    NotificationRecord.NotificationType.ORDER_REJECTED:
        "We're sorry, your order {order} could not be fulfilled. Please contact us for details.",
    NotificationRecord.NotificationType.DELIVERY_DATE_ASSIGNED:
        "Your order {order} is scheduled for delivery on {delivery_date} ({delivery_slot}).",
    NotificationRecord.NotificationType.ORDER_OUT_FOR_DELIVERY:
        "Your order {order} is out for delivery!",
    NotificationRecord.NotificationType.ORDER_DELIVERED:
        "Your order {order} has been delivered. Thank you for shopping with us!",
}


def notify_order_event(order, notification_type):
    """Notifies the customer about their own order.
    Checks customer profile or falls back to order.delivery_phone_number."""
    phone_number = ""
    profile = None
    try:
        profile = getattr(order.customer, "customer_profile", None)
        if profile and profile.whatsapp_number:
            phone_number = profile.whatsapp_number
    except Exception:
        profile = None

    if not phone_number:
        phone_number = getattr(order, "delivery_phone_number", "")

    # If profile exists and user explicitly turned off notifications:
    if profile and hasattr(profile, "whatsapp_notifications_enabled"):
        if not profile.whatsapp_notifications_enabled:
            return None

    if not phone_number:
        return None

    if notification_type == NotificationRecord.NotificationType.ORDER_PLACED:
        message = format_order_placed_message(order)
    elif notification_type == NotificationRecord.NotificationType.ORDER_CONFIRMED:
        message = format_order_approved_message(order)
    elif notification_type == NotificationRecord.NotificationType.DELIVERY_DATE_ASSIGNED:
        message = format_delivery_assigned_message(order)
    else:
        template = _ORDER_EVENT_MESSAGES.get(notification_type)
        if not template:
            return None
        message = template.format(
            order=order.order_number,
            delivery_date=order.delivery_date,
            delivery_slot=order.delivery_time_slot,
        )

    return send_and_record(
        customer=order.customer,
        phone_number=phone_number,
        notification_type=notification_type,
        message=message,
        related_order=order,
        template_id=notification_type,
    )


def notify_farmer_new_order(order):
    """Alerts the farmer's own WhatsApp number that a new order came in.
    Not tied to customer opt-in -- this is the farmer's own business
    alert, configured in Farmer Settings."""
    from apps.payments.models import PaymentSettings  # avoid a hard import cycle at module load

    settings_obj = PaymentSettings.get_settings()
    if not settings_obj.farmer_whatsapp_number:
        return None

    items = order.items.all()
    item_snippets = [f"{item.quantity} {item.unit} {item.product_name}" for item in items[:3]]
    if items.count() > 3:
        item_snippets.append(f"+{items.count() - 3} more")
    item_str = ", ".join(item_snippets) if item_snippets else "Order items"

    message = (
        f"🚨 *New Order Alert!* 🌾\n"
        f"📋 *Order*: {order.order_number}\n"
        f"👤 *Customer*: {order.delivery_full_name} ({order.delivery_phone_number})\n"
        f"💰 *Total*: ₹{order.total} ({order.get_payment_method_display()})\n"
        f"📦 *Items*: {item_str}\n"
        f"📍 *City*: {order.delivery_city}\n\n"
        f"👉 Check your farmer dashboard to confirm and schedule delivery."
    )
    return send_and_record(
        customer=None,
        phone_number=settings_obj.farmer_whatsapp_number,
        notification_type=NotificationRecord.NotificationType.FARMER_NEW_ORDER_ALERT,
        message=message,
        related_order=order,
        template_id="farmer_new_order",
    )


def send_manual_order_notification(order, message, notification_type=NotificationRecord.NotificationType.ORDER_CONFIRMED):
    """Allows farmer to send a manual or custom WhatsApp notification to customer."""
    phone = getattr(order, "delivery_phone_number", "")
    try:
        profile = getattr(order.customer, "customer_profile", None)
        if profile and profile.whatsapp_number:
            phone = profile.whatsapp_number
    except Exception:
        pass

    return send_and_record(
        customer=order.customer,
        phone_number=phone,
        notification_type=notification_type,
        message=message,
        related_order=order,
        template_id="farmer_manual_update",
    )
