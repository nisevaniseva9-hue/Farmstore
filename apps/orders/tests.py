from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Address
from apps.catalog.models import Category, Product
from apps.inventory.services import add_stock, get_available_stock

from .cart import Cart, CartValidationError
from .models import Order, OrderItem, OrderStatusHistory
from .services import EmptyCartError, create_order_from_cart

User = get_user_model()


# ---------------------------------------------------------------------------
# Cart tests (unchanged from Phase 4, kept here for continuity)
# ---------------------------------------------------------------------------

class CartUnitTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(
            name="Mango", category=self.category, price=Decimal("200.00"),
            minimum_order_quantity=Decimal("1"), maximum_order_quantity=Decimal("10"),
        )
        add_stock(self.product, Decimal("5"))

    def _get_cart(self):
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        return Cart(request)

    def test_add_within_limits_succeeds(self):
        cart = self._get_cart()
        cart.add(self.product, Decimal("2"))
        self.assertEqual(len(cart), 1)
        self.assertEqual(cart.get_total_price(), Decimal("400.00"))

    def test_add_more_than_available_stock_rejected(self):
        cart = self._get_cart()
        with self.assertRaises(CartValidationError):
            cart.add(self.product, Decimal("6"))


class CartViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Vegetables")
        self.product = Product.objects.create(name="Tomato", category=self.category, price=Decimal("40.00"))
        add_stock(self.product, Decimal("50"))

    def test_add_to_cart_via_view(self):
        response = self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": "3"})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("orders:cart_detail"))
        self.assertContains(response, "Tomato")


# ---------------------------------------------------------------------------
# Order model tests
# ---------------------------------------------------------------------------

class OrderModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(
            name="Mango", category=self.category, price=Decimal("200.00")
        )

    def test_order_number_auto_generated_and_unique(self):
        customer = User.objects.create_user(username="c1", email="c1@example.com", password="pw12345!")
        o1 = Order.objects.create(
            customer=customer, delivery_full_name="A", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411001", payment_method=Order.PaymentMethod.COD,
        )
        o2 = Order.objects.create(
            customer=customer, delivery_full_name="A", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411001", payment_method=Order.PaymentMethod.COD,
        )
        self.assertTrue(o1.order_number.startswith("FARM-"))
        self.assertNotEqual(o1.order_number, o2.order_number)

    def test_order_item_snapshots_price_and_survives_price_change(self):
        customer = User.objects.create_user(username="c2", email="c2@example.com", password="pw12345!")
        order = Order.objects.create(
            customer=customer, delivery_full_name="A", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411001", payment_method=Order.PaymentMethod.COD,
        )
        item = OrderItem.objects.create(
            order=order, product=self.product, price=self.product.price, quantity=Decimal("2")
        )
        self.assertEqual(item.product_name, "Mango")
        self.assertEqual(item.total, Decimal("400.00"))

        # Farmer changes the price after the order was placed.
        self.product.price = Decimal("500.00")
        self.product.save()
        item.refresh_from_db()

        self.assertEqual(item.price, Decimal("200.00"))  # unchanged historical price
        self.assertEqual(item.total, Decimal("400.00"))  # unchanged historical total

    def test_valid_status_transition(self):
        customer = User.objects.create_user(username="c3", email="c3@example.com", password="pw12345!")
        order = Order.objects.create(
            customer=customer, delivery_full_name="A", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411001", payment_method=Order.PaymentMethod.COD,
        )
        order.transition_to(Order.Status.CONFIRMED, user=customer, note="Looks good")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertTrue(
            OrderStatusHistory.objects.filter(order=order, status=Order.Status.CONFIRMED).exists()
        )

    def test_illegal_status_transition_rejected(self):
        customer = User.objects.create_user(username="c4", email="c4@example.com", password="pw12345!")
        order = Order.objects.create(
            customer=customer, delivery_full_name="A", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411001", payment_method=Order.PaymentMethod.COD,
        )
        # Pending -> Delivered directly is not allowed; must go through
        # confirmed/preparing/etc first.
        with self.assertRaises(ValueError):
            order.transition_to(Order.Status.DELIVERED)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_terminal_status_cannot_transition_further(self):
        customer = User.objects.create_user(username="c5", email="c5@example.com", password="pw12345!")
        order = Order.objects.create(
            customer=customer, delivery_full_name="A", delivery_phone_number="9000000000",
            delivery_line1="L1", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411001", payment_method=Order.PaymentMethod.COD,
        )
        order.transition_to(Order.Status.REJECTED)
        with self.assertRaises(ValueError):
            order.transition_to(Order.Status.CONFIRMED)


# ---------------------------------------------------------------------------
# Checkout service tests -- the atomic all-or-nothing behaviour
# ---------------------------------------------------------------------------

class CreateOrderFromCartTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="shopper", email="shopper@example.com", password="pw12345!"
        )
        self.address = Address.objects.create(
            customer=self.customer, full_name="Shopper S", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001", is_default=True,
        )
        self.category = Category.objects.create(name="Fruits")
        self.mango = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        self.banana = Product.objects.create(name="Banana", category=self.category, price=Decimal("60.00"))
        add_stock(self.mango, Decimal("10"))
        add_stock(self.banana, Decimal("10"))

    def _cart_with(self, items):
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        cart = Cart(request)
        for product, qty in items:
            cart.add(product, qty)
        return cart

    def test_successful_checkout_creates_order_and_reserves_stock(self):
        cart = self._cart_with([(self.mango, Decimal("2")), (self.banana, Decimal("3"))])
        order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal, Decimal("580.00"))  # 2*200 + 3*60
        self.assertEqual(order.total, Decimal("580.00"))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

        self.assertEqual(get_available_stock(self.mango), Decimal("8"))
        self.assertEqual(get_available_stock(self.banana), Decimal("7"))
        self.assertEqual(len(cart), 0)  # cart cleared after successful checkout

    def test_upi_order_starts_as_payment_pending(self):
        cart = self._cart_with([(self.mango, Decimal("1"))])
        order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.UPI,
        )
        # Moves to PENDING_VERIFICATION only once the customer confirms
        # payment on the Phase 7 UPI screen -- not automatically here.
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_empty_cart_raises(self):
        cart = self._cart_with([])
        with self.assertRaises(EmptyCartError):
            create_order_from_cart(
                customer=self.customer, cart=cart, address=self.address,
                payment_method=Order.PaymentMethod.COD,
            )

    def test_insufficient_stock_rolls_back_entire_order(self):
        """The critical atomicity test: mango has enough stock, banana
        doesn't. Nothing about the order should be created -- not the
        Order row, not the mango reservation, not the mango OrderItem."""
        from apps.inventory.services import InsufficientStockError

        cart = self._cart_with([(self.mango, Decimal("2"))])
        # Sneak in a second item that will fail validation at reservation
        # time by directly manipulating the cart's stored quantity past
        # what's available (simulating stock dropping between cart-add and
        # checkout, e.g. another customer buying it in the meantime).
        cart.cart[str(self.banana.pk)] = "999"
        cart._save()

        orders_before = Order.objects.count()

        with self.assertRaises(InsufficientStockError):
            create_order_from_cart(
                customer=self.customer, cart=cart, address=self.address,
                payment_method=Order.PaymentMethod.COD,
            )

        # Nothing committed: no new Order, mango stock untouched.
        self.assertEqual(Order.objects.count(), orders_before)
        self.assertEqual(get_available_stock(self.mango), Decimal("10"))
        self.assertEqual(get_available_stock(self.banana), Decimal("10"))


# ---------------------------------------------------------------------------
# Checkout / order view tests, including authorization
# ---------------------------------------------------------------------------

class CheckoutViewTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw12345!"
        )
        self.other_customer = User.objects.create_user(
            username="other", email="other@example.com", password="pw12345!"
        )
        self.address = Address.objects.create(
            customer=self.customer, full_name="Buyer B", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))

    def test_checkout_requires_login(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response.url)

    def test_checkout_redirects_when_cart_empty(self):
        self.client.login(username="buyer", password="pw12345!")
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("orders:cart_detail"))

    def test_full_checkout_flow_via_client(self):
        self.client.login(username="buyer", password="pw12345!")
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": "2"})

        response = self.client.post(
            reverse("orders:checkout"),
            {"address": self.address.pk, "payment_method": "cod"},
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse("orders:order_detail", args=[order.order_number]))

    def test_customer_cannot_use_another_customers_address_at_checkout(self):
        other_address = Address.objects.create(
            customer=self.other_customer, full_name="Other O", phone_number="9000000001",
            line1="2 Farm Lane", city="Pune", state="MH", postal_code="411002",
        )
        self.client.login(username="buyer", password="pw12345!")
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": "1"})
        response = self.client.post(
            reverse("orders:checkout"),
            {"address": other_address.pk, "payment_method": "cod"},
        )
        # Form validation rejects it (queryset is scoped to request.user's addresses).
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_customer_cannot_view_another_customers_order(self):
        order = Order.objects.create(
            customer=self.other_customer, delivery_full_name="Other O", delivery_phone_number="9000000001",
            delivery_line1="2 Farm Lane", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411002", payment_method=Order.PaymentMethod.COD,
        )
        self.client.login(username="buyer", password="pw12345!")
        response = self.client.get(reverse("orders:order_detail", args=[order.order_number]))
        self.assertEqual(response.status_code, 404)

    def test_order_list_only_shows_own_orders(self):
        Order.objects.create(
            customer=self.other_customer, delivery_full_name="Other O", delivery_phone_number="9000000001",
            delivery_line1="2 Farm Lane", delivery_city="Pune", delivery_state="MH",
            delivery_postal_code="411002", payment_method=Order.PaymentMethod.COD,
        )
        self.client.login(username="buyer", password="pw12345!")
        response = self.client.get(reverse("orders:order_list"))
        self.assertNotContains(response, "Other O")


# ---------------------------------------------------------------------------
# Phase 6: Farmer order management, delivery scheduling, dashboard
# ---------------------------------------------------------------------------

from datetime import date, timedelta

from .services import change_order_status


class ChangeOrderStatusServiceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="buyer2", email="buyer2@example.com", password="pw12345!"
        )
        self.farmer = User.objects.create_user(
            username="farmer2", email="farmer2@example.com", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))

        self.address = Address.objects.create(
            customer=self.customer, full_name="Buyer B", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        cart = self._cart()
        cart.add(self.product, Decimal("3"))
        self.order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )

    def _cart(self):
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        return Cart(request)

    def test_rejecting_order_restores_stock(self):
        self.assertEqual(get_available_stock(self.product), Decimal("7"))  # 10 - 3 reserved
        change_order_status(self.order, Order.Status.REJECTED, user=self.farmer, note="Out of stock elsewhere")
        self.assertEqual(get_available_stock(self.product), Decimal("10"))  # restored
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REJECTED)

    def test_cancelling_confirmed_order_restores_stock(self):
        change_order_status(self.order, Order.Status.CONFIRMED, user=self.farmer)
        change_order_status(self.order, Order.Status.CANCELLED, user=self.farmer, note="Customer request")
        self.assertEqual(get_available_stock(self.product), Decimal("10"))

    def test_delivering_order_does_not_change_stock_further(self):
        change_order_status(self.order, Order.Status.CONFIRMED, user=self.farmer)
        change_order_status(self.order, Order.Status.PREPARING, user=self.farmer)
        change_order_status(self.order, Order.Status.DELIVERY_SCHEDULED, user=self.farmer)
        change_order_status(self.order, Order.Status.OUT_FOR_DELIVERY, user=self.farmer)
        stock_before = get_available_stock(self.product)
        change_order_status(self.order, Order.Status.DELIVERED, user=self.farmer)
        self.assertEqual(get_available_stock(self.product), stock_before)  # unchanged

    def test_full_happy_path_transition_sequence(self):
        for status in [
            Order.Status.CONFIRMED, Order.Status.PREPARING,
            Order.Status.DELIVERY_SCHEDULED, Order.Status.OUT_FOR_DELIVERY,
            Order.Status.DELIVERED,
        ]:
            change_order_status(self.order, status, user=self.farmer)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DELIVERED)
        self.assertEqual(self.order.status_history.count(), 6)  # pending + 5 transitions


class FarmerOrderManagementViewTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="buyer3", email="buyer3@example.com", password="pw12345!"
        )
        self.farmer = User.objects.create_user(
            username="farmer3", email="farmer3@example.com", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(name="Mango", category=self.category, price=Decimal("200.00"))
        add_stock(self.product, Decimal("10"))
        self.address = Address.objects.create(
            customer=self.customer, full_name="Buyer B", phone_number="9123456789",
            line1="1 Farm Lane", city="Pune", state="MH", postal_code="411001",
        )
        cart = self._cart()
        cart.add(self.product, Decimal("2"))
        self.order = create_order_from_cart(
            customer=self.customer, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )

    def _cart(self):
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        return Cart(request)

    def test_customer_cannot_access_farmer_order_list(self):
        self.client.login(username="buyer3", password="pw12345!")
        response = self.client.get(reverse("farmer_orders:order_list"))
        self.assertEqual(response.status_code, 302)

    def test_farmer_can_view_order_list_and_detail(self):
        self.client.login(username="farmer3", password="pw12345!")
        response = self.client.get(reverse("farmer_orders:order_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)

        response = self.client.get(reverse("farmer_orders:order_detail", args=[self.order.order_number]))
        self.assertEqual(response.status_code, 200)

    def test_farmer_can_change_order_status_via_view(self):
        self.client.login(username="farmer3", password="pw12345!")
        response = self.client.post(
            reverse("farmer_orders:order_detail", args=[self.order.order_number]),
            {"change_status": "1", "status": "confirmed", "note": "Looks good"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_customer_cannot_change_order_status(self):
        self.client.login(username="buyer3", password="pw12345!")
        response = self.client.post(
            reverse("farmer_orders:order_detail", args=[self.order.order_number]),
            {"change_status": "1", "status": "confirmed", "note": ""},
        )
        self.assertEqual(response.status_code, 302)  # redirected away, not allowed in
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_farmer_can_assign_delivery_schedule(self):
        self.client.login(username="farmer3", password="pw12345!")
        tomorrow = date.today() + timedelta(days=1)
        response = self.client.post(
            reverse("farmer_orders:order_detail", args=[self.order.order_number]),
            {
                "assign_delivery": "1",
                "delivery_date": tomorrow.isoformat(),
                "delivery_time_slot": "10:00 AM - 1:00 PM",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.delivery_date, tomorrow)
        self.assertEqual(self.order.delivery_time_slot, "10:00 AM - 1:00 PM")

    def test_customer_sees_assigned_delivery_schedule_on_their_order_page(self):
        tomorrow = date.today() + timedelta(days=1)
        self.order.delivery_date = tomorrow
        self.order.delivery_time_slot = "10:00 AM - 1:00 PM"
        self.order.save()

        self.client.login(username="buyer3", password="pw12345!")
        response = self.client.get(reverse("orders:order_detail", args=[self.order.order_number]))
        self.assertContains(response, "10:00 AM - 1:00 PM")

    def test_dashboard_requires_farmer(self):
        response = self.client.get(reverse("farmer_orders:dashboard"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="buyer3", password="pw12345!")
        response = self.client.get(reverse("farmer_orders:dashboard"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="farmer3", password="pw12345!")
        response = self.client.get(reverse("farmer_orders:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Orders")

    def test_customer_list_requires_farmer(self):
        self.client.login(username="buyer3", password="pw12345!")
        response = self.client.get(reverse("farmer_orders:customer_list"))
        self.assertEqual(response.status_code, 302)

        self.client.login(username="farmer3", password="pw12345!")
        response = self.client.get(reverse("farmer_orders:customer_list"))
        self.assertEqual(response.status_code, 200)
