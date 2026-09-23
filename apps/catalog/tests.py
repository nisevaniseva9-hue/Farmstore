from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import ProductImageForm
from .models import Category, Product, ProductImage

User = get_user_model()


def make_image_file(name="test.jpg", content_type="image/jpeg"):
    # Minimal valid 1x1 JPEG bytes
    content = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00" + b"\x08" * 64 +
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"
    )
    return SimpleUploadedFile(name, content, content_type=content_type)


class CategoryModelTests(TestCase):
    def test_slug_auto_generated(self):
        category = Category.objects.create(name="Fresh Fruits")
        self.assertEqual(category.slug, "fresh-fruits")


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Vegetables")

    def test_slug_auto_generated_and_unique(self):
        p1 = Product.objects.create(
            name="Tomato", category=self.category, price=Decimal("40.00")
        )
        p2 = Product.objects.create(
            name="Tomato", category=self.category, price=Decimal("42.00")
        )
        self.assertEqual(p1.slug, "tomato")
        self.assertEqual(p2.slug, "tomato-2")

    def test_new_product_with_no_stock_transactions_is_out_of_stock(self):
        # As of Phase 3, the inventory app tracks real stock. A brand new
        # product with no InventoryTransaction rows has zero available
        # stock until the farmer adds some.
        product = Product.objects.create(
            name="Mango", category=self.category, price=Decimal("200.00")
        )
        self.assertEqual(product.available_stock, Decimal("0"))
        self.assertFalse(product.is_in_stock)

    def test_max_quantity_cannot_be_less_than_min(self):
        from .forms import ProductForm

        form = ProductForm(data={
            "name": "Banana",
            "category": self.category.pk,
            "description": "",
            "price": "60.00",
            "unit": "kg",
            "minimum_order_quantity": "5",
            "maximum_order_quantity": "2",
            "is_active": True,
            "is_featured": False,
        })
        self.assertFalse(form.is_valid())


class ProductImageValidationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fruits")
        self.product = Product.objects.create(
            name="Apple", category=self.category, price=Decimal("150.00")
        )

    def test_rejects_disallowed_extension(self):
        bad_file = SimpleUploadedFile("virus.exe", b"not an image", content_type="application/octet-stream")
        form = ProductImageForm(data={"is_primary": False, "display_order": 0}, files={"image": bad_file})
        self.assertFalse(form.is_valid())

    def test_accepts_valid_jpeg(self):
        good_file = make_image_file()
        form = ProductImageForm(data={"is_primary": True, "display_order": 0}, files={"image": good_file})
        self.assertTrue(form.is_valid(), form.errors)

    def test_only_one_primary_image_per_product(self):
        img1 = ProductImage.objects.create(
            product=self.product, image=make_image_file("a.jpg"), is_primary=True
        )
        img2 = ProductImage.objects.create(
            product=self.product, image=make_image_file("b.jpg"), is_primary=True
        )
        self.assertEqual(
            ProductImage.objects.filter(product=self.product, is_primary=True).count(), 1
        )
        img1.refresh_from_db()
        self.assertFalse(img1.is_primary)
        self.assertTrue(img2.is_primary)


class PublicCatalogViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Milk")
        self.active_product = Product.objects.create(
            name="Cow Milk", category=self.category, price=Decimal("55.00"), unit="litre"
        )
        self.inactive_product = Product.objects.create(
            name="Old Product", category=self.category, price=Decimal("10.00"), is_active=False
        )

    def test_product_list_shows_only_active_products(self):
        response = self.client.get(reverse("catalog:product_list"))
        self.assertContains(response, "Cow Milk")
        self.assertNotContains(response, "Old Product")

    def test_product_detail_page(self):
        response = self.client.get(
            reverse("catalog:product_detail", args=[self.active_product.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cow Milk")

    def test_inactive_product_detail_returns_404(self):
        response = self.client.get(
            reverse("catalog:product_detail", args=[self.inactive_product.slug])
        )
        self.assertEqual(response.status_code, 404)

    def test_category_detail_page(self):
        response = self.client.get(
            reverse("catalog:category_detail", args=[self.category.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cow Milk")


class FarmerCatalogAuthorizationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="cust", email="cust@example.com", password="pw12345!"
        )
        self.farmer = User.objects.create_user(
            username="farmer", email="farmer@example.com", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )
        self.category = Category.objects.create(name="Grains")

    def test_anonymous_redirected_from_farmer_product_list(self):
        response = self.client.get(reverse("farmer_catalog:farmer_product_list"))
        self.assertEqual(response.status_code, 302)

    def test_customer_cannot_access_farmer_dashboard(self):
        self.client.login(username="cust", password="pw12345!")
        response = self.client.get(reverse("farmer_catalog:farmer_product_list"))
        self.assertEqual(response.status_code, 302)  # redirected, not allowed in

    def test_farmer_can_access_and_create_product(self):
        self.client.login(username="farmer", password="pw12345!")
        response = self.client.get(reverse("farmer_catalog:farmer_product_list"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("farmer_catalog:farmer_product_add"),
            {
                "name": "Wheat",
                "category": self.category.pk,
                "description": "Fresh wheat",
                "price": "35.00",
                "unit": "kg",
                "minimum_order_quantity": "1",
                "maximum_order_quantity": "",
                "is_active": "on",
                "is_featured": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(name="Wheat").exists())

    def test_customer_cannot_create_product_via_post(self):
        self.client.login(username="cust", password="pw12345!")
        response = self.client.post(
            reverse("farmer_catalog:farmer_product_add"),
            {
                "name": "Hacked Product",
                "category": self.category.pk,
                "price": "1.00",
                "unit": "kg",
                "minimum_order_quantity": "1",
                "is_active": "on",
            },
        )
        self.assertFalse(Product.objects.filter(name="Hacked Product").exists())


class MobilePhotoUploadAndOptimizationTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            username="farmer2", email="farmer2@example.com", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )
        self.category = Category.objects.create(name="Farm Vegetables")

    def test_farmer_add_product_with_photo(self):
        from .forms import ProductForm
        from PIL import Image
        from io import BytesIO

        # Simulate camera photo
        img = Image.new("RGB", (1600, 1200), color="orange")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        upload = SimpleUploadedFile("carrots.jpg", buf.read(), content_type="image/jpeg")

        self.client.login(username="farmer2", password="pw12345!")
        response = self.client.post(
            reverse("farmer_catalog:farmer_product_add"),
            {
                "name": "Fresh Carrots",
                "category": self.category.pk,
                "description": "Crunchy farm carrots",
                "price": "45.00",
                "unit": "kg",
                "minimum_order_quantity": "1",
                "image": upload,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="Fresh Carrots")
        self.assertEqual(product.images.count(), 1)
        self.assertTrue(product.primary_image.is_primary)

        # Verify image was compressed & resized
        saved_img = Image.open(product.primary_image.image.path)
        self.assertLessEqual(saved_img.width, 1200)
        self.assertLessEqual(saved_img.height, 1200)

    def test_product_image_form_without_display_order(self):
        # Verify that absence of display_order does not cause validation failure
        upload = make_image_file("extra.jpg")
        form = ProductImageForm(data={"is_primary": "on"}, files={"image": upload})
        self.assertTrue(form.is_valid(), f"Errors: {form.errors}")

    def test_annotated_stock_eliminates_query(self):
        from django.db.models import Sum, Value
        from django.db.models.functions import Coalesce

        product = Product.objects.create(
            name="Beetroot", category=self.category, price=Decimal("50.00")
        )
        # Without annotation
        self.assertEqual(product.available_stock, Decimal("0"))

        # With annotation
        annotated_product = Product.objects.filter(pk=product.pk).annotate(
            _annotated_stock=Value(Decimal("42.50"))
        ).first()
        self.assertEqual(annotated_product.available_stock, Decimal("42.50"))
        self.assertTrue(annotated_product.is_in_stock)

    def test_cache_invalidation_on_product_save(self):
        from django.core.cache import cache

        product = Product.objects.create(
            name="Radish", category=self.category, price=Decimal("30.00")
        )
        cache.set("home_page_catalog", "cached_home_data", 300)
        self.assertEqual(cache.get("home_page_catalog"), "cached_home_data")

        # Saving product must invalidate
        product.price = Decimal("32.00")
        product.save()
        self.assertIsNone(cache.get("home_page_catalog"))

    def test_home_page_only_shows_featured_products(self):
        from django.core.cache import cache
        cache.clear()

        Product.objects.create(
            name="Featured Mango",
            category=self.category,
            price=Decimal("150.00"),
            is_active=True,
            is_featured=True,
        )
        Product.objects.create(
            name="Regular Potato",
            category=self.category,
            price=Decimal("30.00"),
            is_active=True,
            is_featured=False,
        )

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Featured Mango")
        self.assertNotContains(response, "Regular Potato")

        # But all products list must still show both
        list_response = self.client.get(reverse("catalog:product_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Featured Mango")
        self.assertContains(list_response, "Regular Potato")
