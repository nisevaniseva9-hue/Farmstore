import threading
from decimal import Decimal

from django import db
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.catalog.models import Category, Product

from .models import InventoryTransaction
from .services import (
    InsufficientStockError,
    add_stock,
    adjust_stock,
    cancel_reservation,
    get_available_stock,
    reserve_stock,
)

User = get_user_model()


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(
            name="Mango", category=self.category, price=Decimal("200.00")
        )

    def test_add_stock_increases_available(self):
        add_stock(self.product, Decimal("100"), note="Opening stock")
        self.assertEqual(get_available_stock(self.product), Decimal("100"))

    def test_add_stock_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            add_stock(self.product, Decimal("0"))
        with self.assertRaises(ValueError):
            add_stock(self.product, Decimal("-5"))

    def test_adjust_stock_can_go_negative_direction(self):
        add_stock(self.product, Decimal("100"))
        adjust_stock(self.product, Decimal("-10"), note="Spoilage")
        self.assertEqual(get_available_stock(self.product), Decimal("90"))

    def test_adjust_stock_rejects_zero(self):
        with self.assertRaises(ValueError):
            adjust_stock(self.product, Decimal("0"))

    def test_reserve_stock_reduces_available(self):
        add_stock(self.product, Decimal("100"))
        reserve_stock(self.product, Decimal("25"), reference="ORD-1")
        self.assertEqual(get_available_stock(self.product), Decimal("75"))

    def test_reserve_stock_raises_when_insufficient(self):
        add_stock(self.product, Decimal("10"))
        with self.assertRaises(InsufficientStockError):
            reserve_stock(self.product, Decimal("11"))
        # Stock must be unchanged after the failed reservation.
        self.assertEqual(get_available_stock(self.product), Decimal("10"))

    def test_cancel_reservation_restores_stock(self):
        add_stock(self.product, Decimal("100"))
        reserve_stock(self.product, Decimal("30"), reference="ORD-2")
        cancel_reservation(self.product, Decimal("30"), reference="ORD-2")
        self.assertEqual(get_available_stock(self.product), Decimal("100"))

    def test_full_audit_trail_nets_out_correctly(self):
        """Add stock, reserve some (sale), reserve-then-cancel some, and
        apply a manual adjustment -- verify the running total reflects
        every transaction exactly, matching the audit-trail spirit of
        the spec's worked example."""
        add_stock(self.product, Decimal("100"), note="Opening stock")
        reserve_stock(self.product, Decimal("25"), reference="sold")          # 100 - 25 = 75
        reserve_stock(self.product, Decimal("5"), reference="to-be-cancelled")  # 75 - 5 = 70
        cancel_reservation(self.product, Decimal("5"), reference="to-be-cancelled")  # 70 + 5 = 75
        adjust_stock(self.product, Decimal("-2"), note="Adjustment")          # 75 - 2 = 73
        self.assertEqual(get_available_stock(self.product), Decimal("73"))
        self.assertEqual(
            InventoryTransaction.objects.filter(product=self.product).count(), 5
        )

    def test_product_available_stock_property_uses_inventory(self):
        add_stock(self.product, Decimal("42"))
        self.assertEqual(self.product.available_stock, Decimal("42"))
        self.assertTrue(self.product.is_in_stock)

    def test_product_out_of_stock_when_zero(self):
        self.assertEqual(self.product.available_stock, Decimal("0"))
        self.assertFalse(self.product.is_in_stock)


class InventoryFarmerAuthorizationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="cust", email="c@example.com", password="pw12345!"
        )
        self.farmer = User.objects.create_user(
            username="farmer", email="f@example.com", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )
        self.category = Category.objects.create(name="Vegetables")
        self.product = Product.objects.create(
            name="Potato", category=self.category, price=Decimal("30.00")
        )

    def test_customer_cannot_add_stock(self):
        self.client.login(username="cust", password="pw12345!")
        response = self.client.post(
            reverse("inventory:add_stock"),
            {"product": self.product.pk, "quantity": "50", "note": ""},
        )
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(get_available_stock(self.product), Decimal("0"))

    def test_farmer_can_add_stock_via_view(self):
        self.client.login(username="farmer", password="pw12345!")
        response = self.client.post(
            reverse("inventory:add_stock"),
            {"product": self.product.pk, "quantity": "50", "note": "Opening"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_available_stock(self.product), Decimal("50"))
        self.assertTrue(
            InventoryTransaction.objects.filter(
                product=self.product, created_by=self.farmer
            ).exists()
        )

    def test_current_stock_page_requires_farmer(self):
        response = self.client.get(reverse("inventory:current_stock"))
        self.assertEqual(response.status_code, 302)


class ConcurrentReservationTests(TransactionTestCase):
    """Real concurrency test: two threads, two separate DB connections,
    racing to reserve stock at the same time. Uses TransactionTestCase
    (not TestCase) so each thread's committed writes are actually
    visible to the other, unlike the wrapping-transaction rollback
    behaviour of a normal TestCase."""

    def setUp(self):
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(
            name="Banana", category=self.category, price=Decimal("60.00")
        )
        add_stock(self.product, Decimal("10"), note="Opening stock")

    def test_only_one_of_two_simultaneous_orders_succeeds_when_stock_is_tight(self):
        """Two 'customers' both try to buy 8 out of 10 available units at
        the same instant. Only one can succeed without overselling."""
        results = {}
        barrier = threading.Barrier(2)

        def attempt_reservation(key):
            barrier.wait()  # maximize the chance both threads overlap
            try:
                reserve_stock(self.product, Decimal("8"), reference=key)
                results[key] = "success"
            except InsufficientStockError:
                results[key] = "rejected"
            finally:
                db.connections.close_all()

        t1 = threading.Thread(target=attempt_reservation, args=("order-a",))
        t2 = threading.Thread(target=attempt_reservation, args=("order-b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        outcomes = list(results.values())
        self.assertEqual(outcomes.count("success"), 1, results)
        self.assertEqual(outcomes.count("rejected"), 1, results)

        # Critically: stock must never go negative.
        final_stock = get_available_stock(self.product)
        self.assertEqual(final_stock, Decimal("2"))
        self.assertGreaterEqual(final_stock, Decimal("0"))
