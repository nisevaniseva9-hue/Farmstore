from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.catalog.models import Category, Product, ProductImage
from apps.inventory.models import InventoryTransaction
from apps.inventory.services import add_stock, get_available_stock


class Command(BaseCommand):
    help = "Seeds authentic farm categories, products, images, and inventory stock from local database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding authentic farm catalog..."))

        # Real farm categories from local project
        categories_data = [
            {
                "name": "Vegetables",
                "slug": "vegetables",
                "description": "",
                "display_order": 0,
            },
            {
                "name": "Fruits",
                "slug": "fruits",
                "description": "Fresh Fruits",
                "display_order": 0,
            },
            {
                "name": "Milk",
                "slug": "milk",
                "description": "Fresh Milk",
                "display_order": 7,
            },
            {
                "name": "Grains",
                "slug": "grains",
                "description": "Grains from our farm",
                "display_order": 0,
            },
            {
                "name": "Eggs",
                "slug": "eggs",
                "description": "Fresh Farm Eggs",
                "display_order": 8,
            },
        ]

        categories = {}
        for cat_info in categories_data:
            cat, created = Category.objects.update_or_create(
                slug=cat_info["slug"],
                defaults={
                    "name": cat_info["name"],
                    "description": cat_info["description"],
                    "display_order": cat_info["display_order"],
                    "is_active": True,
                },
            )
            categories[cat_info["name"]] = cat
            status = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  ✓ {status} category: {cat.name}"))

        # 7 Authentic farm products matching local project database
        products_data = [
            {
                "name": "Tomato",
                "slug": "tomato",
                "category": "Vegetables",
                "description": "Fresh Tomato",
                "price": Decimal("50.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "max_oq": Decimal("10.00"),
                "is_featured": False,
                "image": "products/tomato/tomato-1.png",
                "initial_stock": Decimal("100.00"),
            },
            {
                "name": "Custard Apple",
                "slug": "custard-apple",
                "category": "Fruits",
                "description": "Fresh Custard Apples",
                "price": Decimal("200.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": True,
                "image": "products/custard-apple/custard-apple-2.jpg",
                "initial_stock": Decimal("100.00"),
            },
            {
                "name": "Guava",
                "slug": "guava",
                "category": "Fruits",
                "description": "Fresh Guava",
                "price": Decimal("70.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": True,
                "image": "products/guava/guava-9.jpg",
                "initial_stock": Decimal("50.00"),
            },
            {
                "name": "Pomegranate",
                "slug": "pomegranate",
                "category": "Fruits",
                "description": "Fresh Pomegranates",
                "price": Decimal("300.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": True,
                "image": "products/pomegranate/pomegranate-3.jpg",
                "initial_stock": Decimal("250.00"),
            },
            {
                "name": "Cow Milk",
                "slug": "milk",
                "category": "Milk",
                "description": "Fresh Milk",
                "price": Decimal("80.00"),
                "unit": Product.Unit.LITRE,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": False,
                "image": "products/milk/milk-4.png",
                "initial_stock": Decimal("300.00"),
            },
            {
                "name": "Buffalo Milk",
                "slug": "buffalo-milk",
                "category": "Milk",
                "description": "Fresh Milk",
                "price": Decimal("90.00"),
                "unit": Product.Unit.LITRE,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": False,
                "image": "products/buffalo-milk/buffalo-milk-5.png",
                "initial_stock": Decimal("100.00"),
            },
            {
                "name": "Wheat",
                "slug": "wheat",
                "category": "Grains",
                "description": "Grains from our farm",
                "price": Decimal("30.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": True,
                "image": "products/wheat/wheat-6.jpeg",
                "initial_stock": Decimal("500.00"),
            },
            {
                "name": "Farm Fresh Eggs",
                "slug": "farm-fresh-eggs",
                "category": "Eggs",
                "description": "Naturally laid, high-protein fresh brown farm eggs.",
                "price": Decimal("90.00"),
                "unit": Product.Unit.DOZEN,
                "moq": Decimal("1.00"),
                "max_oq": None,
                "is_featured": True,
                "image": "products/eggs/eggs-1.jpg",
                "initial_stock": Decimal("100.00"),
            },
        ]

        count = 0
        for pdata in products_data:
            cat = categories[pdata["category"]]
            prod, created = Product.objects.update_or_create(
                slug=pdata["slug"],
                defaults={
                    "name": pdata["name"],
                    "category": cat,
                    "description": pdata["description"],
                    "price": pdata["price"],
                    "unit": pdata["unit"],
                    "minimum_order_quantity": pdata["moq"],
                    "maximum_order_quantity": pdata["max_oq"],
                    "is_active": True,
                    "is_featured": pdata["is_featured"],
                },
            )

            # Ensure image is linked
            img_obj, _ = ProductImage.objects.get_or_create(
                product=prod,
                image=pdata["image"],
                defaults={"is_primary": True, "display_order": 0},
            )
            if not img_obj.is_primary:
                img_obj.is_primary = True
                img_obj.save()

            # Ensure stock exists
            current_stock = get_available_stock(prod)
            if current_stock <= 0:
                add_stock(prod, pdata["initial_stock"], note="Initial farm stock seed")

            status = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ {status}: {prod.name} (₹{prod.price}/{prod.get_unit_display()}) - In Stock"
                )
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully configured {count} farm products with photos and stock across {len(categories)} categories!"
            )
        )
