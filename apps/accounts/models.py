"""
Accounts app.

Holds the custom User model (role-based: customer vs farmer/admin), the
CustomerProfile (extra fields specific to customers, including WhatsApp
opt-in), and delivery Address book.
"""
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{10,15}$",
    message="Enter a valid phone number (10-15 digits, optional leading +).",
)


class User(AbstractUser):
    """Custom user so we can cleanly add a role without a fragile
    is_staff/is_superuser-only distinction, and so future custom
    fields don't require a painful migration off django.contrib.auth.User."""

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        FARMER = "farmer", "Farmer/Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    mobile_number = models.CharField(
        max_length=16,
        validators=[phone_validator],
        blank=True,
        default="",
        verbose_name="Admin Mobile Number",
        help_text="Mobile number for Farmer / Admin login and WhatsApp alerts.",
    )

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_farmer(self):
        return self.role == self.Role.FARMER or self.is_superuser


class CustomerProfile(models.Model):
    """One-to-one extension of User holding customer-specific data.
    Kept separate from User so farmer/staff accounts never carry
    irrelevant customer fields."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_profile"
    )
    phone_number = models.CharField(
        max_length=16, validators=[phone_validator], blank=True
    )
    whatsapp_number = models.CharField(
        max_length=16, validators=[phone_validator], blank=True,
        help_text="Number to send WhatsApp notifications to, if different from phone.",
    )
    whatsapp_notifications_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user}"


class Address(models.Model):
    """A customer's delivery address. A customer may have several;
    exactly one may be marked default."""

    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="addresses",
        limit_choices_to={"role": User.Role.CUSTOMER},
    )
    label = models.CharField(
        max_length=50, blank=True, help_text="e.g. Home, Work"
    )
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=16, validators=[phone_validator])
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=12)
    landmark = models.CharField(max_length=255, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.full_name}, {self.city} ({self.customer})"

    def save(self, *args, **kwargs):
        """Ensure only one default address per customer."""
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(customer=self.customer).exclude(
                pk=self.pk
            ).update(is_default=False)
