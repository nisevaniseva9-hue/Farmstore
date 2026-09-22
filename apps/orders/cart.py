"""
Session-based shopping cart.

The cart only ever stores {product_id: quantity} in the session. Price,
product existence, active status, and stock are always re-checked against
the database whenever the cart is read or modified -- the browser's word
for any of that is never trusted, per the project's security requirements.
"""
from decimal import Decimal, InvalidOperation

from apps.catalog.models import Product

SESSION_KEY = "cart"


class CartValidationError(Exception):
    """Raised when a requested cart operation fails server-side validation
    (inactive/missing product, quantity out of allowed range, insufficient
    stock, etc). The message is safe to show to the user."""


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(SESSION_KEY)
        if cart is None:
            cart = {}
            self.session[SESSION_KEY] = cart
        self.cart = cart

    def _save(self):
        self.session[SESSION_KEY] = self.cart
        self.session.modified = True

    @staticmethod
    def _validate_product_and_quantity(product, quantity):
        """Server-side validation. Never trust quantity/price from the client."""
        if not product.is_active:
            raise CartValidationError(f"{product.name} is no longer available.")

        try:
            quantity = Decimal(str(quantity))
        except (InvalidOperation, TypeError):
            raise CartValidationError("Invalid quantity.")

        if quantity <= 0:
            raise CartValidationError("Quantity must be greater than zero.")

        if quantity < product.minimum_order_quantity:
            raise CartValidationError(
                f"Minimum order quantity for {product.name} is "
                f"{product.minimum_order_quantity} {product.get_unit_display()}."
            )

        if product.maximum_order_quantity and quantity > product.maximum_order_quantity:
            raise CartValidationError(
                f"Maximum order quantity for {product.name} is "
                f"{product.maximum_order_quantity} {product.get_unit_display()}."
            )

        available = product.available_stock
        if available is not None and quantity > available:
            raise CartValidationError(
                f"Only {available} {product.get_unit_display()} of {product.name} "
                f"is currently in stock."
            )

        return quantity

    def add(self, product, quantity):
        """Add to cart, or set the quantity if the product is already in
        it (simpler and more predictable for the customer than always
        incrementing)."""
        quantity = self._validate_product_and_quantity(product, quantity)
        self.cart[str(product.pk)] = str(quantity)
        self._save()

    def update(self, product, quantity):
        quantity = self._validate_product_and_quantity(product, quantity)
        self.cart[str(product.pk)] = str(quantity)
        self._save()

    def remove(self, product):
        product_id = str(product.pk)
        if product_id in self.cart:
            del self.cart[product_id]
            self._save()

    def clear(self):
        self.cart = {}
        self._save()

    def __len__(self):
        return len(self.cart)

    def __iter__(self):
        """Yields dicts with live product data and a recalculated
        subtotal, dropping any cart entries whose product has since been
        deleted or deactivated so a stale session never lets someone
        check out with something that's no longer sellable."""
        product_ids = list(self.cart.keys())
        products = Product.objects.filter(pk__in=product_ids, is_active=True)
        products_by_id = {str(p.pk): p for p in products}

        stale_ids = [pid for pid in product_ids if pid not in products_by_id]
        if stale_ids:
            for pid in stale_ids:
                del self.cart[pid]
            self._save()

        for product_id, quantity_str in self.cart.items():
            product = products_by_id.get(product_id)
            if not product:
                continue
            try:
                quantity = Decimal(quantity_str)
            except InvalidOperation:
                continue
            item = {
                "product": product,
                "quantity": quantity,
                "price": product.price,  # always the CURRENT price, never trusted/stored
                "subtotal": product.price * quantity,
            }
            yield item

    def get_total_price(self):
        return sum((item["subtotal"] for item in self), Decimal("0"))

    def get_total_items(self):
        return sum((item["quantity"] for item in self), Decimal("0"))
