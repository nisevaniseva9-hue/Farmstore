"""
Authentication backends.

Customers log in with their mobile number (which is exactly what's stored
in CustomerProfile.phone_number, and also mirrored onto User.username at
registration time -- see forms.CustomerRegistrationForm). Farmer/admin
accounts still log in with a regular username (created via
createsuperuser), so the standard ModelBackend stays enabled too; both
are tried in order (see AUTHENTICATION_BACKENDS in settings.py).
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class PhoneNumberBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, mobile_only=False, **kwargs):
        if not username:
            return None

        from .models import CustomerProfile

        clean_id = str(username).strip().replace(" ", "").replace("-", "")
        user = None

        # 1. Try finding by User.mobile_number (e.g. Admin or Customer mobile)
        if clean_id:
            user = User.objects.filter(mobile_number=clean_id).first()

        # 2. Try finding by CustomerProfile.phone_number
        if not user and clean_id:
            profile = CustomerProfile.objects.filter(phone_number=clean_id).first()
            if profile:
                user = profile.user

        # 3. Try finding by standard User.username (alphanumeric username or phone)
        if not user:
            user = User.objects.filter(username=clean_id).first()

        if not user or not self.user_can_authenticate(user):
            return None

        # Farmer / Admin accounts MUST authenticate with password
        if user.is_farmer:
            if password and user.check_password(password):
                return user
            return None

        # Customer account:
        if mobile_only:
            return user

        if password:
            if user.check_password(password):
                return user
            return None

        # Customer without password (instant 1-tap mobile login)
        return user
