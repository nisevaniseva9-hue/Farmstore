from decimal import Decimal

from django import forms

from apps.catalog.models import Product


class ProductWithUnitChoiceField(forms.ModelChoiceField):
    """Shows the product's category, unit, and current stock right in the
    dropdown label, so it's never ambiguous which product (and which
    unit of measure) you're adding stock for."""

    def label_from_instance(self, product):
        from .services import get_available_stock

        current = get_available_stock(product)
        return (
            f"{product.name} — {product.category.name} "
            f"({product.get_unit_display()}) · currently {current} {product.get_unit_display()}"
        )


class AddStockForm(forms.Form):
    product = ProductWithUnitChoiceField(
        queryset=Product.objects.select_related("category").all()
    )
    quantity = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"),
        help_text="Entered in the product's own unit, shown above (kg, litre, piece, etc).",
    )
    note = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AdjustStockForm(forms.Form):
    product = ProductWithUnitChoiceField(
        queryset=Product.objects.select_related("category").all()
    )
    delta = forms.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Positive to add, negative to remove (e.g. -2.5 for spoilage). Uses the product's own unit, shown above.",
    )
    note = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_delta(self):
        delta = self.cleaned_data["delta"]
        if delta == 0:
            raise forms.ValidationError("Adjustment cannot be zero.")
        return delta
