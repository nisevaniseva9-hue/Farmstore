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
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            user = User.objects.get(
                role=User.Role.CUSTOMER, customer_profile__phone_number=username
            )
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
