from django.conf import settings


def farm_info(request):
    """Makes farm name/tagline, active categories, and cart size
    available in every template without every view having to pass them
    explicitly."""
    from apps.catalog.models import Category
    from apps.orders.cart import Cart

    return {
        "FARM_NAME": settings.FARM_NAME,
        "FARM_TAGLINE": settings.FARM_TAGLINE,
        "NAV_CATEGORIES": Category.objects.filter(is_active=True),
        "CART_ITEM_COUNT": len(Cart(request)),
    }
