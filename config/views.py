from django.http import HttpResponse
from django.shortcuts import render

from apps.catalog.models import Category, Product


def home(request):
    categories = Category.objects.filter(is_active=True)
    featured_products = Product.objects.filter(
        is_active=True, is_featured=True
    ).select_related("category")[:8]
    if not featured_products:
        featured_products = Product.objects.filter(
            is_active=True
        ).select_related("category")[:8]
    return render(
        request, "home.html",
        {"categories": categories, "featured_products": featured_products},
    )


def health_check(request):
    """Simple health endpoint for deployment checks / uptime monitors."""
    return HttpResponse("OK")
