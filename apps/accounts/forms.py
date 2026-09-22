from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Address, CustomerProfile, User, phone_validator


class CustomerRegistrationForm(UserCreationForm):
    """Simple registration for customers: name, phone number, password.
    No separate username -- the phone number IS the login identifier
    (stored internally as User.username so we don't have to touch
    Django's built-in auth machinery). Farmer accounts are created via
    the Django admin / createsuperuser, never through public signup."""

    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=False, label="Last Name")
    phone_number = forms.CharField(
        max_length=16, required=True, validators=[phone_validator],
        label="Mobile Number",
        help_text="You'll use this number to log in.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UserCreationForm normally includes a 'username' field -- drop it,
        # the phone number takes its place.
        self.fields.pop("username", None)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"]
        if User.objects.filter(username=phone_number).exists():
            raise ValidationError("An account with this mobile number already exists.")
        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["phone_number"]
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
            CustomerProfile.objects.create(
                user=user, phone_number=self.cleaned_data["phone_number"]
            )
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False, help_text="Optional.")

    class Meta:
        model = CustomerProfile
        fields = [
            "phone_number",
            "whatsapp_number",
            "whatsapp_notifications_enabled",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["email"].initial = self.user.email
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"]
        # Changing your phone number effectively changes your login ID
        # (username == phone number), so keep them in sync and guard
        # against colliding with someone else's number.
        if User.objects.filter(username=phone_number).exclude(pk=self.user.pk).exists():
            raise ValidationError("Another account is already using this mobile number.")
        return phone_number

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"]
        self.user.username = self.cleaned_data["phone_number"]
        if commit:
            self.user.save()
            profile.save()
        return profile


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "label", "full_name", "phone_number", "line1", "line2",
            "city", "state", "postal_code", "landmark", "is_default",
        ]


class PhoneOrUsernameAuthenticationForm(forms.Form):
    """Login form: customers type their mobile number, farmer/admin types
    their username. Kept as one plain field since both backends are tried
    automatically -- the person doesn't have to pick which kind of login
    this is."""

    username = forms.CharField(label="Mobile Number", widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"class": "form-control"}))

    error_messages = {
        "invalid_login": "Please check your mobile number/username and password and try again.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        from django.contrib.auth import authenticate

        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise ValidationError(self.error_messages["invalid_login"])
        return self.cleaned_data

    def get_user(self):
        return self.user_cache
