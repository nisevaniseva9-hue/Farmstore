from django.http import HttpResponse
from django.shortcuts import render

from apps.catalog.models import Category, Product


def home(request):
    categories = Category.objects.filter(is_active=True).order_by("display_order", "name")
    products = Product.objects.filter(
        is_active=True
    ).select_related("category").prefetch_related("images").order_by("name")
    return render(
        request, "home.html",
        {"categories": categories, "products": products},
    )


def health_check(request):
    """Simple health endpoint for deployment checks / uptime monitors."""
    return HttpResponse("OK")
