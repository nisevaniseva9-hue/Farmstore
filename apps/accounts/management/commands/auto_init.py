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
        admin_username = config("ADMIN_USERNAME", default="admin").strip()

        # 1. Create or update primary Farmer Admin account (username="admin", mobile="9325780114")
        user = User.objects.filter(username=admin_username).first()
        if not user:
            user = User.objects.create(
                username=admin_username,
                role=User.Role.FARMER,
                is_staff=True,
                is_superuser=True,
                first_name="Abdul",
                last_name="Rauf",
                mobile_number=admin_phone,
            )
            user.set_password(admin_password)
            user.save()
            action = "Created"
        else:
            updated_fields = []
            if user.role != User.Role.FARMER:
                user.role = User.Role.FARMER
                updated_fields.append("role")
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                updated_fields.extend(["is_staff", "is_superuser"])
            if user.mobile_number != admin_phone:
                user.mobile_number = admin_phone
                updated_fields.append("mobile_number")
            if not user.check_password(admin_password):
                user.set_password(admin_password)
                updated_fields.append("password")
            if updated_fields:
                user.save()
                action = f"Updated ({', '.join(updated_fields)})"
            else:
                action = "Verified (no changes)"

        # Also ensure legacy user with username=admin_phone has mobile_number set
        if admin_phone != admin_username:
            phone_user = User.objects.filter(username=admin_phone).first()
            if phone_user and phone_user.mobile_number != admin_phone:
                phone_user.mobile_number = admin_phone
                phone_user.save(update_fields=["mobile_number"])

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        if profile.phone_number != admin_phone or not profile.whatsapp_number:
            profile.phone_number = admin_phone
            profile.whatsapp_number = "8552813624"
            profile.whatsapp_notifications_enabled = True
            profile.save()

        # Set farmer notification number and payment settings
        try:
            ps = PaymentSettings.get_settings()
            ps_updated = False
            if not ps.farmer_whatsapp_number:
                ps.farmer_whatsapp_number = "8552813624"
                ps_updated = True
            if not ps.upi_id or ps.upi_id == "abc@hdfc":
                ps.upi_id = "9325780114@ibl"
                ps_updated = True
            if not ps.upi_display_name:
                ps.upi_display_name = "ARBAJ RAFIK SAYYAD"
                ps_updated = True
            if not ps.qr_code_image:
                ps.qr_code_image = "payment_settings/upi_qr.jpg"
                ps_updated = True
            if ps_updated:
                ps.save()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"PaymentSettings notice: {e}"))

        self.stdout.write(
            self.style.SUCCESS(f"✓ {action} Farmer Admin ({admin_phone}) successfully.")
        )

        self.stdout.write(self.style.SUCCESS("✓ Auto-initialization completed successfully!"))
