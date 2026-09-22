from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Address
from apps.catalog.models import Category, Product
from apps.inventory.services import add_stock
from apps.orders.cart import Cart
from apps.orders.models import Order
from apps.orders.services import create_order_from_cart

from .models import PaymentSettings
from .services import (
    CashOnDeliveryPaymentService,
    ManualUpiPaymentService,
    PaymentServiceError,
    get_payment_service,
)

User = get_user_model()


def make_cart():
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    return Cart(request)


class PaymentSettingsModelTests(TestCase):
    def test_singleton_always_pk_one(self):
        s1 = PaymentSettings.get_settings()
        s1.upi_id = "farmer@upi"
        s1.save()
        s2 = PaymentSettings.get_settings()
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(s2.upi_id, "farmer@upi")
        self.assertEqual(PaymentSettings.objects.count(), 1)

    def test_is_configured_reflects_upi_id_presence(self):
        settings_obj = PaymentSettings.get_settings()
        self.assertFalse(settings_obj.is_configured)
        settings_obj.upi_id = "farm@upi"
        settings_obj.save()
        self.assertTrue(settings_obj.is_configured)


class PaymentServiceAbstractionTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="payer", email="payer@example.com", password="pw12345!"
        )
        self.address = Address.objects.create(
            customer=self.customer, full_name="Payer P", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))

    def _make_upi_order(self):
        cart = make_cart()
        cart.add(self.product, Decimal("1"))
        return create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.UPI,
        )

    def test_get_payment_service_returns_correct_implementation(self):
        self.assertIsInstance(get_payment_service(Order.PaymentMethod.UPI), ManualUpiPaymentService)
        self.assertIsInstance(get_payment_service(Order.PaymentMethod.COD), CashOnDeliveryPaymentService)

    def test_unknown_payment_method_raises(self):
        with self.assertRaises(PaymentServiceError):
            get_payment_service("bitcoin")

    def test_submit_for_verification_moves_status_correctly(self):
        order = self._make_upi_order()
        service = ManualUpiPaymentService()
        service.submit_for_verification(order, reference="UTR123")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING_VERIFICATION)
        self.assertEqual(order.payment_reference, "UTR123")

    def test_cannot_submit_for_verification_twice(self):
        order = self._make_upi_order()
        service = ManualUpiPaymentService()
        service.submit_for_verification(order)
        with self.assertRaises(PaymentServiceError):
            service.submit_for_verification(order)

    def test_submit_for_verification_rejects_cod_order(self):
        cart = make_cart()
        cart.add(self.product, Decimal("1"))
        cod_order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )
        service = ManualUpiPaymentService()
        with self.assertRaises(PaymentServiceError):
            service.submit_for_verification(cod_order)

    def test_verify_marks_paid(self):
        order = self._make_upi_order()
        service = ManualUpiPaymentService()
        service.submit_for_verification(order)
        service.verify(order, user=None)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_reject_marks_failed(self):
        order = self._make_upi_order()
        service = ManualUpiPaymentService()
        service.submit_for_verification(order)
        service.reject(order, user=None, reason="No matching transaction")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)


class CustomerUpiFlowViewTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="c_upi", email="c_upi@example.com", password="pw12345!"
        )
        self.other_customer = User.objects.create_user(
            username="c_other", email="c_other@example.com", password="pw12345!"
        )
        self.address = Address.objects.create(
            customer=self.customer, full_name="C U", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))
        PaymentSettings.get_settings()  # ensure it exists

    def test_full_checkout_with_upi_redirects_to_pay_screen(self):
        self.client.login(username="c_upi", password="pw12345!")
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": "1"})
        response = self.client.post(
            reverse("orders:checkout"),
            {"address": self.address.pk, "payment_method": "upi"},
        )
        order = Order.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse("payments:pay_upi", args=[order.order_number]))
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_i_have_paid_moves_to_pending_verification(self):
        cart = make_cart()
        # Use the client's session-based cart via view instead, simpler:
        self.client.login(username="c_upi", password="pw12345!")
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": "1"})
        self.client.post(
            reverse("orders:checkout"), {"address": self.address.pk, "payment_method": "upi"}
        )
        order = Order.objects.get(customer=self.customer)

        response = self.client.post(
            reverse("payments:pay_upi", args=[order.order_number]), {"reference": "UTR999"}
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING_VERIFICATION)
        self.assertEqual(order.payment_reference, "UTR999")

    def test_customer_cannot_access_another_customers_pay_screen(self):
        order = Order.objects.create(
            customer=self.other_customer, delivery_full_name="X", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH", delivery_postal_code="411001",
            payment_method=Order.PaymentMethod.UPI,
        )
        self.client.login(username="c_upi", password="pw12345!")
        response = self.client.get(reverse("payments:pay_upi", args=[order.order_number]))
        self.assertEqual(response.status_code, 404)


class FarmerPaymentManagementTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="c_verify", email="c_verify@example.com", password="pw12345!"
        )
        self.farmer = User.objects.create_user(
            username="f_verify", email="f_verify@example.com", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )
        self.address = Address.objects.create(
            customer=self.customer, full_name="C V", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))

        cart = make_cart()
        cart.add(self.product, Decimal("1"))
        self.order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.UPI,
        )
        ManualUpiPaymentService().submit_for_verification(self.order, reference="UTR1")

    def test_customer_cannot_verify_own_payment(self):
        self.client.login(username="c_verify", password="pw12345!")
        response = self.client.post(
            reverse("farmer_payments:verify_payment", args=[self.order.order_number]),
            {"approve": "1"},
        )
        self.assertEqual(response.status_code, 302)  # redirected to login, not allowed in
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING_VERIFICATION)

    def test_farmer_can_approve_payment(self):
        self.client.login(username="f_verify", password="pw12345!")
        response = self.client.post(
            reverse("farmer_payments:verify_payment", args=[self.order.order_number]),
            {"approve": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_farmer_can_reject_payment(self):
        self.client.login(username="f_verify", password="pw12345!")
        response = self.client.post(
            reverse("farmer_payments:verify_payment", args=[self.order.order_number]),
            {"reject": "1", "reason": "No matching transaction found"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

    def test_pending_verifications_list_shows_order(self):
        self.client.login(username="f_verify", password="pw12345!")
        response = self.client.get(reverse("farmer_payments:pending_verifications"))
        self.assertContains(response, self.order.order_number)

    def test_farmer_settings_requires_farmer(self):
        response = self.client.get(reverse("farmer_payments:payment_settings"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="c_verify", password="pw12345!")
        response = self.client.get(reverse("farmer_payments:payment_settings"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="f_verify", password="pw12345!")
        response = self.client.get(reverse("farmer_payments:payment_settings"))
        self.assertEqual(response.status_code, 200)

    def test_farmer_can_update_upi_settings(self):
        self.client.login(username="f_verify", password="pw12345!")
        response = self.client.post(
            reverse("farmer_payments:payment_settings"),
            {"upi_id": "farm@upi", "upi_display_name": "Farm Fresh"},
        )
        self.assertEqual(response.status_code, 302)
        settings_obj = PaymentSettings.get_settings()
        self.assertEqual(settings_obj.upi_id, "farm@upi")
