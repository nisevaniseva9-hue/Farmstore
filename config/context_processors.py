from django.conf import settings
from django.core.cache import cache


def farm_info(request):
    """Makes farm name/tagline, active categories, and cart size
    available in every template without every view having to pass them
    explicitly."""
    from apps.catalog.models import Category
    from apps.orders.cart import Cart

    categories = cache.get("nav_categories")
    if categories is None:
        categories = list(Category.objects.filter(is_active=True).order_by("display_order", "name"))
        cache.set("nav_categories", categories, 3600)

    return {
        "FARM_NAME": settings.FARM_NAME,
        "FARM_TAGLINE": settings.FARM_TAGLINE,
        "NAV_CATEGORIES": categories,
        "CART_ITEM_COUNT": len(Cart(request)),
    }
