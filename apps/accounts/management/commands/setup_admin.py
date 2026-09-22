from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import CustomerProfile
from apps.payments.models import PaymentSettings

User = get_user_model()


class Command(BaseCommand):
    help = "Creates or updates a Farmer Admin / Superuser account with full access"

    def add_arguments(self, parser):
        parser.add_argument("--phone", type=str, help="10-digit mobile number for farmer login")
        parser.add_argument("--password", type=str, help="Password for farmer login")

    def handle(self, *args, **options):
        phone = options.get("phone")
        password = options.get("password")

        if not phone:
            phone = input("Enter Farmer Phone Number (e.g. 9876543210): ").strip()
        if not password:
            import getpass
            password = getpass.getpass("Enter Password: ").strip()

        if not phone or not password:
            self.stdout.write(self.style.ERROR("Phone number and password are required."))
            return

        user, created = User.objects.get_or_create(username=phone)
        user.role = User.Role.FARMER
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.phone_number = phone
        profile.whatsapp_number = phone
        profile.whatsapp_notifications_enabled = True
        profile.save()

        # Also configure farmer alert phone number in PaymentSettings
        try:
            settings_obj = PaymentSettings.get_settings()
            settings_obj.farmer_whatsapp_number = phone
            settings_obj.save()
        except Exception:
            pass

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 {action} Farmer Admin account successfully!\n"
                f"   Login Phone: {phone}\n"
                f"   Role: Farmer / Admin\n"
                f"   Farmer Dashboard: /farmer/\n"
                f"   Django Admin: /admin/\n"
            )
        )
