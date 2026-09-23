from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render

from apps.catalog.models import Category, Product

HOME_CACHE_KEY = "home_page_catalog"
HOME_CACHE_TIMEOUT = 300  # 5 minutes


def home(request):
    cached_data = cache.get(HOME_CACHE_KEY)
    if cached_data is not None:
        categories, products = cached_data
    else:
        categories = list(Category.objects.filter(is_active=True).order_by("display_order", "name"))
        products = list(
            Product.objects.filter(is_active=True)
            .annotate(_annotated_stock=Coalesce(Sum("inventory_transactions__quantity"), Value(Decimal("0"))))
            .select_related("category")
            .prefetch_related("images")
            .order_by("name")
        )
        cache.set(HOME_CACHE_KEY, (categories, products), HOME_CACHE_TIMEOUT)

    return render(
        request,
        "home.html",
        {"categories": categories, "products": products},
    )


def health_check(request):
    """Simple health endpoint for deployment checks / uptime monitors."""
    return HttpResponse("OK")

