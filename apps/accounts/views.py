from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .forms import AddressForm, CustomerRegistrationForm, PhoneOrUsernameAuthenticationForm, ProfileForm
from .models import Address, CustomerProfile


class FarmLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = PhoneOrUsernameAuthenticationForm

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user, backend="apps.accounts.backends.PhoneNumberBackend")
        return redirect(self.get_success_url())


class FarmLogoutView(LogoutView):
    next_page = "home"


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    next_url = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="apps.accounts.backends.PhoneNumberBackend")
            messages.success(request, f"Welcome to Farm Fresh, {user.first_name}!")
            if next_url:
                return redirect(next_url)
            return redirect("home")
    else:
        form = CustomerRegistrationForm()
    return render(request, "accounts/register.html", {"form": form, "next": next_url})


@login_required
def profile(request):
    if request.user.is_farmer:
        messages.info(request, "That page is for customer accounts. Here's your dashboard.")
        return redirect("farmer_orders:dashboard")

    profile_obj, _created = CustomerProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile_obj, user=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def address_list(request):
    addresses = request.user.addresses.all()
    return render(request, "accounts/address_list.html", {"addresses": addresses})


@login_required
def address_create(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        form = AddressForm(request.POST, user=request.user)
        if form.is_valid():
            address = form.save(commit=False)
            address.customer = request.user
            address.save()
            messages.success(request, "Address saved successfully.")
            if next_url:
                return redirect(next_url)
            return redirect("accounts:address_list")
    else:
        form = AddressForm(user=request.user)
    return render(request, "accounts/address_form.html", {"form": form, "next": next_url})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, customer=request.user)
    next_url = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated.")
            if next_url:
                return redirect(next_url)
            return redirect("accounts:address_list")
    else:
        form = AddressForm(instance=address, user=request.user)
    return render(request, "accounts/address_form.html", {"form": form, "next": next_url})


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, customer=request.user)
    if request.method == "POST":
        address.delete()
        messages.success(request, "Address removed.")
        return redirect("accounts:address_list")
    return render(request, "accounts/address_confirm_delete.html", {"address": address})
