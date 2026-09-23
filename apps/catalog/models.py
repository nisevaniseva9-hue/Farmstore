"""
Catalog app: Category and Product, plus ProductImage.

Farmer manages these through the custom farmer dashboard (not the public
Django admin, though admin registration is also provided for convenience/
break-glass access).
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def invalidate_catalog_cache():
    try:
        from django.core.cache import cache
        cache.delete("home_page_catalog")
        cache.delete("catalog_products")
    except Exception:
        pass


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        invalidate_catalog_cache()

    def delete(self, *args, **kwargs):
        res = super().delete(*args, **kwargs)
        invalidate_catalog_cache()
        return res

    def get_absolute_url(self):
        return reverse("catalog:category_detail", kwargs={"slug": self.slug})


class Product(models.Model):
    class Unit(models.TextChoices):
        KG = "kg", "Kilogram"
        GRAM = "gram", "Gram"
        LITRE = "litre", "Litre"
        PIECE = "piece", "Piece"
        DOZEN = "dozen", "Dozen"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    minimum_order_quantity = models.DecimalField(
        max_digits=8, decimal_places=2, default=1, validators=[MinValueValidator(0.01)]
    )
    maximum_order_quantity = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Leave blank for no maximum.",
    )
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)
        invalidate_catalog_cache()

    def delete(self, *args, **kwargs):
        res = super().delete(*args, **kwargs)
        invalidate_catalog_cache()
        return res

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def primary_image(self):
        if hasattr(self, "_prefetched_objects_cache") and "images" in self._prefetched_objects_cache:
            for img in self.images.all():
                if img.is_primary:
                    return img
            return next(iter(self.images.all()), None)
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def available_stock(self):
        """Delegates to the inventory app (Phase 3+). Returns None if the
        inventory app isn't installed yet, so templates degrade gracefully."""
        if hasattr(self, "_annotated_stock"):
            return self._annotated_stock
        if hasattr(self, "_cached_available_stock"):
            return self._cached_available_stock
        from django.apps import apps as django_apps

        if not django_apps.is_installed("apps.inventory"):
            return None
        from apps.inventory.services import get_available_stock

        stock = get_available_stock(self)
        self._cached_available_stock = stock
        return stock

    @property
    def is_in_stock(self):
        stock = self.available_stock
        if stock is None:
            return True  # inventory not tracked yet (pre-Phase 3)
        return stock > 0


def product_image_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    safe_name = slugify(instance.product.slug or "product")
    return f"products/{safe_name}/{safe_name}-{instance.pk or 'new'}.{ext}"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=product_image_upload_path)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            ProductImage.objects.filter(product=self.product).exclude(
                pk=self.pk
            ).update(is_primary=False)
        invalidate_catalog_cache()

    def delete(self, *args, **kwargs):
        res = super().delete(*args, **kwargs)
        invalidate_catalog_cache()
        return res
