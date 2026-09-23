from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Address, CustomerProfile, User


@admin.register(User)
class FarmUserAdmin(UserAdmin):
    list_display = ("username", "mobile_number", "email", "first_name", "last_name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "mobile_number", "first_name", "last_name", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Admin Contact & Role", {"fields": ("role", "mobile_number")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Admin Contact & Role", {"fields": ("role", "mobile_number")}),
    )


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "whatsapp_notifications_enabled")
    search_fields = ("user__username", "user__email", "phone_number")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("customer", "full_name", "city", "is_default")
    list_filter = ("state", "is_default")
    search_fields = ("full_name", "city", "postal_code", "customer__username")
