from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Product

from .cart import Cart, CartValidationError
from .forms import CartAddForm, CheckoutForm
from .models import Order
from .services import EmptyCartError, create_order_from_cart
from apps.inventory.services import InsufficientStockError


def cart_detail(request):
    cart = Cart(request)
    return render(request, "cart/cart_detail.html", {"cart": cart})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    form = CartAddForm(request.POST)
    cart = Cart(request)
    if form.is_valid():
        try:
            cart.add(product, form.cleaned_data["quantity"])
            messages.success(request, f"{product.name} added to your cart.")
        except CartValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Please enter a valid quantity.")

    next_url = request.POST.get("next") or product.get_absolute_url()
    return redirect(next_url)


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    form = CartAddForm(request.POST)
    cart = Cart(request)
    if form.is_valid():
        try:
            cart.update(product, form.cleaned_data["quantity"])
            messages.success(request, "Cart updated.")
        except CartValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Please enter a valid quantity.")
    return redirect("orders:cart_detail")


@require_POST
def cart_remove(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    cart = Cart(request)
    cart.remove(product)
    messages.success(request, f"{product.name} removed from your cart.")
    return redirect("orders:cart_detail")


@require_POST
def cart_clear(request):
    cart = Cart(request)
    cart.clear()
    messages.success(request, "Your cart has been cleared.")
    return redirect("orders:cart_detail")


@login_required
def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.info(request, "Your cart is empty. Add something before checking out.")
        return redirect("orders:cart_detail")

    if not request.user.addresses.exists():
        messages.info(request, "Please add a delivery address before checking out.")
        return redirect("accounts:address_create")

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            address = form.cleaned_data["address"]
            # Ownership check: a customer must never be able to check out
            # using another customer's saved address, even by guessing an
            # ID. ModelChoiceField's queryset is already scoped to this
            # user's addresses, so an out-of-scope pk simply fails
            # validation -- but we double-check defensively here too.
            if address.customer_id != request.user.id:
                messages.error(request, "Invalid delivery address.")
                return redirect("orders:checkout")

            try:
                order = create_order_from_cart(
                    customer=request.user,
                    cart=cart,
                    address=address,
                    payment_method=form.cleaned_data["payment_method"],
                )
            except InsufficientStockError as exc:
                messages.error(request, str(exc))
            except EmptyCartError:
                messages.info(request, "Your cart is empty.")
                return redirect("orders:cart_detail")
            else:
                messages.success(request, f"Order {order.order_number} placed successfully!")
                if order.payment_method == Order.PaymentMethod.UPI:
                    return redirect("payments:pay_upi", order_number=order.order_number)
                return redirect("orders:order_detail", order_number=order.order_number)
    else:
        form = CheckoutForm(user=request.user)

    return render(request, "checkout/checkout.html", {"form": form, "cart": cart})


@login_required
def order_list(request):
    orders = request.user.orders.all()
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail(request, order_number):
    # get_object_or_404 filtered by customer=request.user means a
    # customer requesting another customer's order number gets a plain
    # 404, never a peek at someone else's order.
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, "orders/order_detail.html", {"order": order})

