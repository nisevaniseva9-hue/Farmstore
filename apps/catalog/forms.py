from io import BytesIO
from PIL import Image, ImageOps

from django import forms
from django.core.files.uploadedfile import InMemoryUploadedFile

from .models import Category, Product, ProductImage


MAX_IMAGE_SIZE_MB = 15
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _validate_and_compress_image(image):
    ext = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise forms.ValidationError(
            "Unsupported file type. Please upload a JPG, PNG, or WEBP image."
        )

    if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise forms.ValidationError(
            f"Image must be smaller than {MAX_IMAGE_SIZE_MB}MB."
        )

    content_type = getattr(image, "content_type", "")
    if content_type and not content_type.startswith("image/"):
        raise forms.ValidationError("Uploaded file is not a valid image.")

    try:
        image.seek(0)
        pil_img = Image.open(image)
        # Correct orientation from mobile cameras (EXIF rotation)
        pil_img = ImageOps.exif_transpose(pil_img)

        img_format = pil_img.format or "JPEG"
        if img_format.upper() in ("JPEG", "JPG"):
            if pil_img.mode in ("RGBA", "P"):
                pil_img = pil_img.convert("RGB")
            img_format = "JPEG"
        elif img_format.upper() == "PNG":
            if pil_img.mode not in ("RGBA", "RGB", "L"):
                pil_img = pil_img.convert("RGBA")
        elif img_format.upper() == "WEBP":
            pass
        else:
            if pil_img.mode in ("RGBA", "P"):
                pil_img = pil_img.convert("RGB")
            img_format = "JPEG"

        # Resize large smartphone photos to max 1200px width/height
        max_dimension = 1200
        if pil_img.width > max_dimension or pil_img.height > max_dimension:
            pil_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        output = BytesIO()
        if img_format == "JPEG":
            pil_img.save(output, format="JPEG", quality=85, optimize=True)
            new_content_type = "image/jpeg"
        elif img_format == "WEBP":
            pil_img.save(output, format="WEBP", quality=85)
            new_content_type = "image/webp"
        else:
            pil_img.save(output, format=img_format, optimize=True)
            new_content_type = f"image/{img_format.lower()}"

        output.seek(0)
        filename = image.name
        if img_format == "JPEG" and not (filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg")):
            filename = f"{filename.rsplit('.', 1)[0]}.jpg"

        return InMemoryUploadedFile(
            file=output,
            field_name=getattr(image, "field_name", "image"),
            name=filename,
            content_type=new_content_type,
            size=output.getbuffer().nbytes,
            charset=None,
        )
    except forms.ValidationError:
        raise
    except Exception:
        try:
            image.seek(0)
            return image
        except Exception:
            raise forms.ValidationError("Unable to process image. Please try another photo.")


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
    image = forms.ImageField(
        required=False,
        label="Product Photo",
        help_text="Take a photo with camera or choose from gallery (JPG, PNG, WEBP).",
        widget=forms.FileInput(attrs={"accept": "image/*", "class": "form-control"}),
    )

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

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return None
        return _validate_and_compress_image(image)

    def clean(self):
        cleaned = super().clean()
        min_qty = cleaned.get("minimum_order_quantity")
        max_qty = cleaned.get("maximum_order_quantity")
        if min_qty and max_qty and max_qty < min_qty:
            raise forms.ValidationError(
                "Maximum order quantity cannot be less than the minimum order quantity."
            )
        return cleaned


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["image", "is_primary"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs.update({
            "class": "form-control",
            "accept": "image/*",
        })

    def clean_image(self):
        image = self.cleaned_data["image"]
        return _validate_and_compress_image(image)
