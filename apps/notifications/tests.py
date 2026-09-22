from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Address, CustomerProfile
from apps.catalog.models import Category, Product
from apps.inventory.services import add_stock
from apps.orders.cart import Cart
from apps.orders.models import Order
from apps.orders.services import assign_delivery, change_order_status, create_order_from_cart
from apps.payments.models import PaymentSettings

from .models import NotificationRecord
from .services import (
    WhatsAppNotConfiguredError,
    WhatsAppNotificationService,
    notify_customers_stock_available,
    notify_farmer_new_order,
    notify_order_event,
    send_and_record,
)

User = get_user_model()


def make_cart():
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    return Cart(request)


@override_settings(WHATSAPP_PROVIDER="meta")
class SendAndRecordTests(TestCase):
    """WHATSAPP_API_TOKEN is blank in test settings (see .env.example
    defaults), so these exercise the 'not configured -> skipped, but
    still recorded' path -- which is exactly the default state a fresh
    checkout of this project will be in until someone adds real
    WhatsApp credentials."""

    def test_no_phone_number_is_skipped_and_recorded(self):
        record = send_and_record(
            customer=None, phone_number="", notification_type="new_stock_available",
            message="hello",
        )
        self.assertEqual(record.delivery_status, NotificationRecord.DeliveryStatus.SKIPPED)
        self.assertTrue(record.error_message)

    def test_unconfigured_service_is_skipped_and_recorded_not_raised(self):
        # Must NEVER raise -- this is the whole point of send_and_record.
        record = send_and_record(
            customer=None, phone_number="9123456780", notification_type="new_stock_available",
            message="hello",
        )
        self.assertEqual(record.delivery_status, NotificationRecord.DeliveryStatus.SKIPPED)

    @override_settings(WHATSAPP_API_TOKEN="fake-token", WHATSAPP_PHONE_NUMBER_ID="12345")
    @patch.object(WhatsAppNotificationService, "_call_api")
    def test_configured_and_successful_send_is_recorded_sent(self, mock_call):
        mock_call.return_value = {"messages": [{"id": "wamid.abc"}]}
        record = send_and_record(
            customer=None, phone_number="9123456780", notification_type="new_stock_available",
            message="hello",
        )
        self.assertEqual(record.delivery_status, NotificationRecord.DeliveryStatus.SENT)
        mock_call.assert_called_once()

    @override_settings(WHATSAPP_API_TOKEN="fake-token", WHATSAPP_PHONE_NUMBER_ID="12345")
    @patch.object(WhatsAppNotificationService, "_call_api")
    def test_api_failure_is_recorded_failed_not_raised(self, mock_call):
        mock_call.side_effect = Exception("Network error")
        record = send_and_record(
            customer=None, phone_number="9123456780", notification_type="new_stock_available",
            message="hello",
        )
        self.assertEqual(record.delivery_status, NotificationRecord.DeliveryStatus.FAILED)
        self.assertIn("Network error", record.error_message)


class StockAvailableNotificationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))

        self.opted_in = User.objects.create_user(username="9111111111", password="pw12345!")
        CustomerProfile.objects.create(
            user=self.opted_in, phone_number="9111111111", whatsapp_number="9111111111",
            whatsapp_notifications_enabled=True,
        )
        self.opted_out = User.objects.create_user(username="9222222222", password="pw12345!")
        CustomerProfile.objects.create(
            user=self.opted_out, phone_number="9222222222", whatsapp_number="9222222222",
            whatsapp_notifications_enabled=False,
        )

    def test_only_opted_in_customers_notified(self):
        records = notify_customers_stock_available(self.product)
        notified_customers = {r.customer for r in records}
        self.assertIn(self.opted_in, notified_customers)
        self.assertNotIn(self.opted_out, notified_customers)

    def test_add_stock_auto_notifies_when_going_from_zero_to_available(self):
        self.assertEqual(NotificationRecord.objects.count(), 0)
        add_stock(self.product, Decimal("50"))
        self.assertTrue(
            NotificationRecord.objects.filter(
                notification_type=NotificationRecord.NotificationType.NEW_STOCK_AVAILABLE,
                related_product=self.product,
            ).exists()
        )

    def test_add_stock_does_not_renotify_when_already_in_stock(self):
        add_stock(self.product, Decimal("50"))
        count_after_first = NotificationRecord.objects.count()
        add_stock(self.product, Decimal("20"))  # already in stock, no new "available" event
        self.assertEqual(NotificationRecord.objects.count(), count_after_first)

    def test_manual_notify_view_requires_farmer(self):
        response = self.client.post(reverse("inventory:notify_customers", args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="9222222222", password="pw12345!")
        response = self.client.post(reverse("inventory:notify_customers", args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)  # redirected, not the farmer dashboard

    def test_farmer_can_manually_trigger_notification(self):
        farmer = User.objects.create_user(
            username="farmer_notif", password="pw12345!", role=User.Role.FARMER, is_staff=True
        )
        self.client.login(username="farmer_notif", password="pw12345!")
        before = NotificationRecord.objects.count()
        response = self.client.post(reverse("inventory:notify_customers", args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertGreater(NotificationRecord.objects.count(), before)


class OrderNotificationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="9333333333", password="pw12345!")
        CustomerProfile.objects.create(
            user=self.customer, phone_number="9333333333", whatsapp_number="9333333333",
            whatsapp_notifications_enabled=True,
        )
        self.address = Address.objects.create(
            customer=self.customer, full_name="C", phone_number="9333333333",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))

        settings_obj = PaymentSettings.get_settings()
        settings_obj.farmer_whatsapp_number = "9000000099"
        settings_obj.save()

        cart = make_cart()
        cart.add(self.product, Decimal("2"))
        self.order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )

    def test_order_placed_notifies_farmer(self):
        self.assertTrue(
            NotificationRecord.objects.filter(
                notification_type=NotificationRecord.NotificationType.FARMER_NEW_ORDER_ALERT,
                related_order=self.order, phone_number="9000000099",
            ).exists()
        )

    def test_order_placed_notifies_opted_in_customer(self):
        self.assertTrue(
            NotificationRecord.objects.filter(
                notification_type=NotificationRecord.NotificationType.ORDER_PLACED,
                related_order=self.order, customer=self.customer,
            ).exists()
        )

    def test_order_confirmed_notifies_customer(self):
        change_order_status(self.order, Order.Status.CONFIRMED)
        self.assertTrue(
            NotificationRecord.objects.filter(
                notification_type=NotificationRecord.NotificationType.ORDER_CONFIRMED,
                related_order=self.order,
            ).exists()
        )

    def test_delivery_assignment_notifies_customer(self):
        from datetime import date, timedelta

        assign_delivery(self.order, date.today() + timedelta(days=1), "10 AM - 1 PM")
        self.assertTrue(
            NotificationRecord.objects.filter(
                notification_type=NotificationRecord.NotificationType.DELIVERY_DATE_ASSIGNED,
                related_order=self.order,
            ).exists()
        )

    def test_no_farmer_alert_when_number_not_configured(self):
        settings_obj = PaymentSettings.get_settings()
        settings_obj.farmer_whatsapp_number = ""
        settings_obj.save()
        result = notify_farmer_new_order(self.order)
        self.assertIsNone(result)


class FarmerNotificationListViewTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            username="farmer_view_notif", password="pw12345!", role=User.Role.FARMER, is_staff=True
        )

    def test_requires_farmer(self):
        response = self.client.get(reverse("farmer_notifications:notification_list"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="farmer_view_notif", password="pw12345!")
        response = self.client.get(reverse("farmer_notifications:notification_list"))
        self.assertEqual(response.status_code, 200)

    def test_simulator_view_requires_farmer(self):
        response = self.client.get(reverse("farmer_notifications:notification_test"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="farmer_view_notif", password="pw12345!")
        response = self.client.get(reverse("farmer_notifications:notification_test"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WhatsApp Simulator")


class WhatsAppRichMessageAndProviderTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="9555555555", password="pw12345!")
        self.address = Address.objects.create(
            customer=self.customer, full_name="Rajesh Kumar", phone_number="9555555555",
            line1="Flat 402, Green Meadows", city="Pune", state="MH", postal_code="411001",
        )
        self.category = Category.objects.create(name="Vegetables")
        self.product1 = Product.objects.create(name="Fresh Tomato", category=self.category, price=Decimal("40.00"), unit=Product.Unit.KG)
        self.product2 = Product.objects.create(name="Organic Spinach", category=self.category, price=Decimal("30.00"), unit=Product.Unit.KG)
        add_stock(self.product1, Decimal("20"))
        add_stock(self.product2, Decimal("20"))

        cart = make_cart()
        cart.add(self.product1, Decimal("2"))
        cart.add(self.product2, Decimal("1"))
        self.order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )

    def test_order_placed_message_includes_all_products_and_totals(self):
        from .services import format_order_placed_message
        msg = format_order_placed_message(self.order)
        self.assertIn("Fresh Tomato", msg)
        self.assertIn("Organic Spinach", msg)
        self.assertIn("40.00", msg)
        self.assertIn("110.00", msg)  # 2*40 + 1*30 = 110
        self.assertIn("Rajesh Kumar", msg)
        self.assertIn(self.order.order_number, msg)

    def test_order_approved_message_includes_status_and_delivery(self):
        from .services import format_order_approved_message
        from datetime import date
        self.order.delivery_date = date(2026, 9, 25)
        self.order.delivery_time_slot = "Morning 8am-11am"
        self.order.save()

        msg = format_order_approved_message(self.order)
        self.assertIn("Approved & Confirmed", msg)
        self.assertIn("25 Sep 2026", msg)
        self.assertIn("Morning 8am-11am", msg)
        self.assertIn(self.order.order_number, msg)

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_console_provider_simulates_sending(self):
        record = send_and_record(
            customer=self.customer, phone_number="9555555555",
            notification_type=NotificationRecord.NotificationType.ORDER_PLACED,
            message="Simulated order placed",
        )
        self.assertEqual(record.delivery_status, NotificationRecord.DeliveryStatus.SIMULATED)

    @override_settings(
        WHATSAPP_PROVIDER="twilio",
        TWILIO_ACCOUNT_SID="AC12345",
        TWILIO_AUTH_TOKEN="token123",
        TWILIO_WHATSAPP_FROM="whatsapp:+14155238886",
    )
    @patch.object(WhatsAppNotificationService, "_call_twilio_api")
    def test_twilio_provider_send(self, mock_twilio):
        mock_twilio.return_value = {"sid": "SM123"}
        record = send_and_record(
            customer=self.customer, phone_number="9555555555",
            notification_type=NotificationRecord.NotificationType.ORDER_PLACED,
            message="Twilio order placed",
        )
        self.assertEqual(record.delivery_status, NotificationRecord.DeliveryStatus.SENT)
        mock_twilio.assert_called_once()

