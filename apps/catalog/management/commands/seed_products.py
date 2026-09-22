from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.catalog.models import Category, Product
from apps.inventory.services import add_stock, get_available_stock


class Command(BaseCommand):
    help = "Seeds initial organic categories, products, and inventory stock"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding farm categories and products..."))

        categories_data = [
            {
                "name": "Fresh Vegetables",
                "description": "Crisp, naturally grown farm vegetables harvested daily.",
                "display_order": 1,
            },
            {
                "name": "Fresh Fruits",
                "description": "Naturally ripened, sweet, seasonal organic fruits.",
                "display_order": 2,
            },
            {
                "name": "Dairy & Ghee",
                "description": "Pure A2 cow milk, butter, and traditional bilona ghee.",
                "display_order": 3,
            },
            {
                "name": "Grains & Pulses",
                "description": "Unpolished organic grains, daal, and heritage rice varieties.",
                "display_order": 4,
            },
            {
                "name": "Herbs & Greens",
                "description": "Fresh culinary herbs and leafy greens from our garden.",
                "display_order": 5,
            },
        ]

        categories = {}
        for cat_info in categories_data:
            cat, created = Category.objects.get_or_create(
                name=cat_info["name"],
                defaults={
                    "slug": slugify(cat_info["name"]),
                    "description": cat_info["description"],
                    "display_order": cat_info["display_order"],
                    "is_active": True,
                },
            )
            categories[cat.name] = cat
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + Created category: {cat.name}"))

        products_data = [
            {
                "name": "Organic Desi Tomatoes",
                "category": "Fresh Vegetables",
                "description": "Plump, sun-ripened farm fresh tomatoes bursting with authentic country flavor.",
                "price": Decimal("40.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "is_featured": True,
                "initial_stock": Decimal("50.00"),
            },
            {
                "name": "Farm Fresh Potatoes",
                "category": "Fresh Vegetables",
                "description": "Locally harvested earthy potatoes, perfect for daily curries and roasting.",
                "price": Decimal("35.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "is_featured": False,
                "initial_stock": Decimal("80.00"),
            },
            {
                "name": "Crunchy Red Carrots",
                "category": "Fresh Vegetables",
                "description": "Sweet, organic tender carrots rich in vitamins and beta-carotene.",
                "price": Decimal("50.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("0.50"),
                "is_featured": True,
                "initial_stock": Decimal("40.00"),
            },
            {
                "name": "Organic Palak (Spinach)",
                "category": "Herbs & Greens",
                "description": "Tender, iron-rich green spinach leaves freshly cut every morning.",
                "price": Decimal("30.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "is_featured": True,
                "initial_stock": Decimal("35.00"),
            },
            {
                "name": "Fresh Coriander (Dhaniya)",
                "category": "Herbs & Greens",
                "description": "Aromatic, fresh green coriander leaves harvested with roots intact.",
                "price": Decimal("20.00"),
                "unit": Product.Unit.PIECE,
                "moq": Decimal("1.00"),
                "is_featured": False,
                "initial_stock": Decimal("45.00"),
            },
            {
                "name": "Alphonso Mangoes (Hapus)",
                "category": "Fresh Fruits",
                "description": "Naturally tree-ripened Ratnagiri Alphonso mangoes with rich aroma.",
                "price": Decimal("350.00"),
                "unit": Product.Unit.DOZEN,
                "moq": Decimal("1.00"),
                "is_featured": True,
                "initial_stock": Decimal("25.00"),
            },
            {
                "name": "Sweet Kinnow Oranges",
                "category": "Fresh Fruits",
                "description": "Juicy, citrus-rich oranges direct from Punjab orchards.",
                "price": Decimal("80.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "is_featured": False,
                "initial_stock": Decimal("30.00"),
            },
            {
                "name": "Pure Gir Cow A2 Milk",
                "category": "Dairy & Ghee",
                "description": "Raw, unadulterated whole milk from grass-fed desi Gir cows.",
                "price": Decimal("75.00"),
                "unit": Product.Unit.LITRE,
                "moq": Decimal("1.00"),
                "is_featured": True,
                "initial_stock": Decimal("50.00"),
            },
            {
                "name": "Desi Bilona Cow Ghee",
                "category": "Dairy & Ghee",
                "description": "Hand-churned Vedic bilona method ghee from curd with golden granular texture.",
                "price": Decimal("750.00"),
                "unit": Product.Unit.PIECE,
                "moq": Decimal("1.00"),
                "is_featured": True,
                "initial_stock": Decimal("15.00"),
            },
            {
                "name": "Organic Basmati Heritage Rice",
                "category": "Grains & Pulses",
                "description": "Aged traditional long-grain basmati with natural aroma and fluffiness.",
                "price": Decimal("125.00"),
                "unit": Product.Unit.KG,
                "moq": Decimal("1.00"),
                "is_featured": False,
                "initial_stock": Decimal("60.00"),
            },
        ]

        count = 0
        for pdata in products_data:
            cat = categories[pdata["category"]]
            prod, created = Product.objects.get_or_create(
                name=pdata["name"],
                category=cat,
                defaults={
                    "slug": slugify(pdata["name"]),
                    "description": pdata["description"],
                    "price": pdata["price"],
                    "unit": pdata["unit"],
                    "minimum_order_quantity": pdata["moq"],
                    "is_active": True,
                    "is_featured": pdata["is_featured"],
                },
            )
            # Ensure stock exists
            current_stock = get_available_stock(prod)
            if current_stock <= 0:
                add_stock(prod, pdata["initial_stock"], note="Initial catalog seed")

            status = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ {status}: {prod.name} (₹{prod.price}/{prod.get_unit_display()}) - Stock: {pdata['initial_stock']}"
                )
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully seeded {count} organic farm products across {len(categories)} categories!")
        )
