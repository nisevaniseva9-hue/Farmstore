from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "unit", "price", "quantity")
    can_delete = False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("status", "changed_by", "note", "created_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "customer", "status", "payment_method",
        "payment_status", "total", "created_at",
    )
    list_filter = ("status", "payment_method", "payment_status")
    search_fields = ("order_number", "customer__username", "customer__email")
    readonly_fields = ("order_number", "subtotal", "delivery_charge", "total", "created_at", "updated_at")
    inlines = [OrderItemInline, OrderStatusHistoryInline]
