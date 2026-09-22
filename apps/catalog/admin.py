from django.contrib import admin

from .models import Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "display_order")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "unit", "is_active", "is_featured")
    list_filter = ("category", "is_active", "is_featured", "unit")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]
