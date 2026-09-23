from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from decouple import config
from apps.accounts.models import CustomerProfile
from apps.payments.models import PaymentSettings

User = get_user_model()


class Command(BaseCommand):
    help = "Automatically sets up the default farmer admin and seeds the product catalog on boot"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting auto-initialization..."))

        admin_phone = config("ADMIN_PHONE", default="9325780114").strip()
        admin_password = config("ADMIN_PASSWORD", default="Farmer@18").strip()

        # 1. Create or update Farmer Admin account
        user, created = User.objects.get_or_create(username=admin_phone)
        user.role = User.Role.FARMER
        user.is_staff = True
        user.is_superuser = True
        user.first_name = "Abdul"
        user.last_name = "Rauf"
        user.set_password(admin_password)
        user.save()

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.phone_number = admin_phone
        profile.whatsapp_number = "8552813624"
        profile.whatsapp_notifications_enabled = True
        profile.save()

        # Set farmer notification number and payment settings
        try:
            ps = PaymentSettings.get_settings()
            ps.farmer_whatsapp_number = "8552813624"
            ps.upi_id = ps.upi_id or "abc@hdfc"
            ps.upi_display_name = "Abdul Rauf (Farmer)"
            ps.qr_code_image = ps.qr_code_image or "payment_settings/upi_qr.jpg"
            ps.save()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"PaymentSettings notice: {e}"))

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"✓ {action} Farmer Admin ({admin_phone}) successfully.")
        )

        self.stdout.write(self.style.SUCCESS("✓ Auto-initialization completed successfully!"))
