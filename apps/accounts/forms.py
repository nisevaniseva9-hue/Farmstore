from django import forms
from django.core.exceptions import ValidationError

from .models import Address, CustomerProfile, User, phone_validator


class CustomerRegistrationForm(forms.ModelForm):
    """Frictionless registration for customers: name and mobile number only.
    No password is required. The phone number is the login identifier."""

    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="First Name / Full Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter your name", "autofocus": True}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label="Last Name (Optional)",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )
    phone_number = forms.CharField(
        max_length=16,
        required=True,
        validators=[phone_validator],
        label="Mobile Number",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "10-digit mobile number", "type": "tel"}),
        help_text="You will use this number to log in and receive order updates.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name"]

    def clean_phone_number(self):
        phone_number = str(self.cleaned_data["phone_number"]).strip().replace(" ", "").replace("-", "")
        if not phone_number.isdigit() and not (phone_number.startswith("+") and phone_number[1:].isdigit()):
            raise ValidationError("Please enter a valid 10-digit mobile number.")
        if len(phone_number) == 10:
            phone_number = phone_number
        if User.objects.filter(username=phone_number).exists():
            raise ValidationError("An account with this mobile number already exists. Please log in directly.")
        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        phone = self.cleaned_data["phone_number"]
        user.username = phone
        user.role = User.Role.CUSTOMER
        pwd = self.data.get("password1") or self.data.get("password")
        if pwd:
            user.set_password(pwd)
        else:
            user.set_unusable_password()
        if commit:
            user.save()
            CustomerProfile.objects.create(
                user=user, phone_number=phone
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
    """Simplified 5-field address form:
    1. Building Name
    2. Flat No and Wing
    3. Area or Locality
    4. City
    5. Pincode
    """

    building_name = forms.CharField(
        max_length=255,
        required=False,
        label="Building Name / Society",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. HM Royal Society"}),
    )
    flat_wing = forms.CharField(
        max_length=255,
        required=False,
        label="Flat No and Wing",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Flat 402, A Wing"}),
    )
    area = forms.CharField(
        max_length=255,
        required=False,
        label="Area",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Kondhwa"}),
    )
    locality = forms.CharField(
        max_length=255,
        required=False,
        label="Locality / Landmark",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Opposite to Talab Factory"}),
    )
    area_locality = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.HiddenInput(),
    )

    city = forms.CharField(
        max_length=100,
        required=True,
        label="City",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Pune"}),
    )
    postal_code = forms.CharField(
        max_length=12,
        required=True,
        label="Pincode",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 411048"}),
    )
    full_name = forms.CharField(
        max_length=150,
        required=False,
        label="Receiver's Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Receiver's Name (Optional)"}),
    )
    phone_number = forms.CharField(
        max_length=16,
        required=False,
        label="Contact Mobile",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Receiver's Mobile (Optional)", "type": "tel"}),
    )

    class Meta:
        model = Address
        fields = ["city", "postal_code"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["flat_wing"].initial = self.instance.line1
            self.fields["building_name"].initial = self.instance.line2
            if self.instance.landmark:
                if ", " in self.instance.landmark:
                    parts = self.instance.landmark.split(", ", 1)
                    self.fields["area"].initial = parts[0]
                    self.fields["locality"].initial = parts[1]
                else:
                    self.fields["area"].initial = self.instance.landmark
            self.fields["full_name"].initial = self.instance.full_name
            self.fields["phone_number"].initial = self.instance.phone_number
        elif self.user:
            self.fields["full_name"].initial = self.user.get_full_name() or self.user.first_name
            self.fields["phone_number"].initial = getattr(self.user, "username", "")

    def clean(self):
        cleaned_data = super().clean()
        fw = cleaned_data.get("flat_wing") or self.data.get("flat_wing") or self.data.get("line1")
        bn = cleaned_data.get("building_name") or self.data.get("building_name") or self.data.get("line2") or ""
        ar = cleaned_data.get("area") or self.data.get("area") or ""
        loc = cleaned_data.get("locality") or self.data.get("locality") or ""
        al = cleaned_data.get("area_locality") or self.data.get("area_locality") or self.data.get("landmark") or ""

        if not fw:
            self.add_error("flat_wing", "Please enter Flat No and Wing (or Address line 1).")

        cleaned_data["flat_wing"] = fw or ""
        cleaned_data["building_name"] = bn or ""
        cleaned_data["area"] = ar or ""
        cleaned_data["locality"] = loc or ""
        cleaned_data["area_locality"] = al or ""
        return cleaned_data

    def save(self, commit=True):
        address = super().save(commit=False)
        address.line1 = self.cleaned_data.get("flat_wing") or self.data.get("line1") or ""
        address.line2 = self.cleaned_data.get("building_name") or self.data.get("line2") or ""

        ar = self.cleaned_data.get("area") or self.data.get("area") or ""
        loc = self.cleaned_data.get("locality") or self.data.get("locality") or ""
        if ar and loc:
            combined_landmark = f"{ar}, {loc}"
        elif ar:
            combined_landmark = ar
        elif loc:
            combined_landmark = loc
        else:
            combined_landmark = self.cleaned_data.get("area_locality") or self.data.get("area_locality") or self.data.get("landmark") or ""

        address.landmark = combined_landmark

        full_name = self.cleaned_data.get("full_name") or self.data.get("full_name")
        if not full_name and self.user:
            full_name = self.user.get_full_name() or self.user.first_name
        address.full_name = full_name or "Customer"

        phone = self.cleaned_data.get("phone_number") or self.data.get("phone_number")
        if not phone and self.user:
            phone = getattr(self.user, "username", "")
        address.phone_number = phone or "0000000000"

        if not address.state:
            address.state = self.data.get("state") or "Maharashtra"
        if not address.label:
            address.label = self.data.get("label") or "Home"
        if "is_default" in self.data:
            address.is_default = self.data.get("is_default") in ("on", "true", "True", True, 1, "1")
        if commit:
            address.save()
        return address


class PhoneOrUsernameAuthenticationForm(forms.Form):
    """Login form:
    Customers log in frictionless with just their Mobile Number.
    Farmer / Admin accounts enter Username/Phone + Password."""

    username = forms.CharField(
        label="Mobile Number",
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Enter 10-digit mobile number",
            "autofocus": True,
            "type": "tel",
        }),
    )
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Farmer Admin password",
        }),
    )

    error_messages = {
        "invalid_login": "Please check your mobile number/username and password and try again.",
        "admin_password_required": "Administrator login requires a password. Please enter your password.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        from django.contrib.auth import authenticate

        username = str(self.cleaned_data.get("username", "")).strip().replace(" ", "").replace("-", "")
        password = self.cleaned_data.get("password", "")

        if not username:
            return self.cleaned_data

        target_user = User.objects.filter(username=username).first()
        if not target_user:
            target_user = User.objects.filter(mobile_number=username).first()
        if not target_user:
            profile = CustomerProfile.objects.filter(phone_number=username).first()
            if profile:
                target_user = profile.user

        if not target_user:
            raise ValidationError("No account found with this username or mobile number. Please check and try again!")

        # Farmer / Admin accounts MUST authenticate with password
        if target_user.is_farmer:
            if not password:
                raise ValidationError(self.error_messages["admin_password_required"])
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise ValidationError("Incorrect password for Administrator account.")
            return self.cleaned_data

        # Customer account:
        if password:
            auth_user = authenticate(self.request, username=username, password=password)
            if auth_user:
                self.user_cache = auth_user
                return self.cleaned_data
            else:
                raise ValidationError(self.error_messages["invalid_login"])

        # Instant 1-tap mobile login if no password was supplied
        auth_user = authenticate(self.request, username=username, mobile_only=True)
        self.user_cache = auth_user or target_user
        return self.cleaned_data

    def get_user(self):
        return self.user_cache

