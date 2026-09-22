from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .forms import AddStockForm, AdjustStockForm
from .models import InventoryTransaction
from .services import add_stock, adjust_stock, get_available_stock


def _is_farmer(user):
    return user.is_authenticated and user.is_farmer


farmer_required = user_passes_test(_is_farmer, login_url="accounts:login")

LOW_STOCK_THRESHOLD = 10


@farmer_required
def current_stock(request):
    products = Product.objects.select_related("category").all()
    rows = []
    for product in products:
        stock = get_available_stock(product)
        rows.append({
            "product": product,
            "stock": stock,
            "is_low": stock <= LOW_STOCK_THRESHOLD,
        })
    return render(request, "farmer/inventory/current_stock.html", {"rows": rows})


@farmer_required
def add_stock_view(request):
    if request.method == "POST":
        form = AddStockForm(request.POST)
        if form.is_valid():
            add_stock(
                product=form.cleaned_data["product"],
                quantity=form.cleaned_data["quantity"],
                user=request.user,
                note=form.cleaned_data["note"],
            )
            messages.success(
                request,
                f"Added {form.cleaned_data['quantity']} {form.cleaned_data['product'].unit} "
                f"of {form.cleaned_data['product'].name}.",
            )
            return redirect("inventory:current_stock")
    else:
        form = AddStockForm()
    return render(request, "farmer/inventory/add_stock.html", {"form": form})


@farmer_required
def adjust_stock_view(request):
    if request.method == "POST":
        form = AdjustStockForm(request.POST)
        if form.is_valid():
            adjust_stock(
                product=form.cleaned_data["product"],
                delta=form.cleaned_data["delta"],
                user=request.user,
                note=form.cleaned_data["note"],
            )
            messages.success(request, "Stock adjustment recorded.")
            return redirect("inventory:current_stock")
    else:
        form = AdjustStockForm()
    return render(request, "farmer/inventory/adjust_stock.html", {"form": form})


@farmer_required
def inventory_history(request, product_pk=None):
    transactions = InventoryTransaction.objects.select_related("product", "created_by")
    product = None
    if product_pk:
        product = get_object_or_404(Product, pk=product_pk)
        transactions = transactions.filter(product=product)
    transactions = transactions[:200]
    return render(
        request, "farmer/inventory/history.html",
        {"transactions": transactions, "product": product},
    )


@farmer_required
@require_POST
def notify_customers(request, product_pk):
    """Manual 'notify customers this is available' button -- independent
    of the automatic 0-to-available trigger in add_stock(), for
    re-announcing something or catching cases the automatic trigger
    missed."""
    from apps.notifications.services import notify_customers_stock_available

    product = get_object_or_404(Product, pk=product_pk)
    records = notify_customers_stock_available(product)
    sent = sum(1 for r in records if r.delivery_status == "sent")
    if not records:
        messages.info(request, "No customers have opted into WhatsApp notifications yet.")
    else:
        messages.success(
            request,
            f"Notification sent to {sent} of {len(records)} opted-in customer(s) for {product.name}.",
        )
    return redirect("inventory:current_stock")
