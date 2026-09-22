from django import forms

from .models import Category, Product, ProductImage


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "is_active", "display_order"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name", "category", "description", "price", "unit",
            "minimum_order_quantity", "maximum_order_quantity",
            "is_active", "is_featured",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        min_qty = cleaned.get("minimum_order_quantity")
        max_qty = cleaned.get("maximum_order_quantity")
        if min_qty and max_qty and max_qty < min_qty:
            raise forms.ValidationError(
                "Maximum order quantity cannot be less than the minimum order quantity."
            )
        return cleaned


MAX_IMAGE_SIZE_MB = 5
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["image", "is_primary", "display_order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs.setdefault("class", "form-control")

    def clean_image(self):
        image = self.cleaned_data["image"]

        ext = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise forms.ValidationError(
                "Unsupported file type. Use JPG, PNG, or WEBP."
            )

        if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"Image must be smaller than {MAX_IMAGE_SIZE_MB}MB."
            )

        content_type = getattr(image, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError("Uploaded file is not a valid image.")

        return image
