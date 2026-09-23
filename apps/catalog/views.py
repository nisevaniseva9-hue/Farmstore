from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CategoryForm, ProductForm, ProductImageForm
from .models import Category, Product, ProductImage


# ---------------------------------------------------------------------------
# Public / customer-facing views
# ---------------------------------------------------------------------------

def category_list(request):
    categories = Category.objects.filter(is_active=True).order_by("display_order", "name")
    return render(request, "catalog/category_list.html", {"categories": categories})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = (
        category.products.filter(is_active=True)
        .annotate(_annotated_stock=Coalesce(Sum("inventory_transactions__quantity"), Value(Decimal("0"))))
        .select_related("category")
        .prefetch_related("images")
        .order_by("name")
    )
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request, "catalog/category_detail.html",
        {"category": category, "page_obj": page_obj},
    )


def product_list(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    products = (
        Product.objects.filter(is_active=True)
        .annotate(_annotated_stock=Coalesce(Sum("inventory_transactions__quantity"), Value(Decimal("0"))))
        .select_related("category")
        .prefetch_related("images")
        .order_by("name")
    )
    if query:
        products = products.filter(name__icontains=query)
    if category_slug:
        products = products.filter(category__slug=category_slug)
    categories = Category.objects.filter(is_active=True).order_by("display_order", "name")
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "catalog/product_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "category_slug": category_slug,
            "categories": categories,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.annotate(
            _annotated_stock=Coalesce(Sum("inventory_transactions__quantity"), Value(Decimal("0")))
        ).select_related("category").prefetch_related("images"),
        slug=slug,
        is_active=True,
    )
    return render(request, "catalog/product_detail.html", {"product": product})


# ---------------------------------------------------------------------------
# Farmer-only administration views
# ---------------------------------------------------------------------------

def _is_farmer(user):
    return user.is_authenticated and user.is_farmer


farmer_required = user_passes_test(_is_farmer, login_url="accounts:login")


@farmer_required
def farmer_product_list(request):
    products = Product.objects.select_related("category").all()
    return render(request, "farmer/catalog/product_list.html", {"products": products})


@farmer_required
def farmer_product_add(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            image_file = form.cleaned_data.get("image")
            if image_file:
                ProductImage.objects.create(product=product, image=image_file, is_primary=True)
            messages.success(request, f"Product '{product.name}' created.")
            return redirect("farmer_catalog:farmer_product_edit", pk=product.pk)
    else:
        form = ProductForm()
    return render(request, "farmer/catalog/product_form.html", {"form": form})


@farmer_required
def farmer_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            image_file = form.cleaned_data.get("image")
            if image_file:
                is_first = not product.images.filter(is_primary=True).exists()
                ProductImage.objects.create(product=product, image=image_file, is_primary=is_first)
            messages.success(request, "Product updated.")
            return redirect("farmer_catalog:farmer_product_edit", pk=product.pk)
    else:
        form = ProductForm(instance=product)

    image_form = ProductImageForm()
    return render(
        request, "farmer/catalog/product_form.html",
        {"form": form, "product": product, "image_form": image_form},
    )


@farmer_required
def farmer_product_image_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.product = product
            if not product.images.filter(is_primary=True).exists():
                image.is_primary = True
            image.save()
            messages.success(request, "Image uploaded successfully.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error if field in ("__all__", "image") else f"{field}: {error}")
    return redirect("farmer_catalog:farmer_product_edit", pk=product.pk)


@farmer_required
def farmer_product_image_delete(request, pk, image_pk):
    product = get_object_or_404(Product, pk=pk)
    image = get_object_or_404(product.images, pk=image_pk)
    if request.method == "POST":
        image.delete()
        messages.success(request, "Image removed.")
    return redirect("farmer_catalog:farmer_product_edit", pk=product.pk)


@farmer_required
def farmer_category_list(request):
    categories = Category.objects.all()
    return render(request, "farmer/catalog/category_list.html", {"categories": categories})


@farmer_required
def farmer_category_add(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
            return redirect("farmer_catalog:farmer_category_list")
    else:
        form = CategoryForm()
    return render(request, "farmer/catalog/category_form.html", {"form": form})


@farmer_required
def farmer_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect("farmer_catalog:farmer_category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "farmer/catalog/category_form.html", {"form": form})
