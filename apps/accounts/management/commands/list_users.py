from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Lists all registered users, their roles, and admin status"

    def handle(self, *args, **options):
        users = User.objects.all().order_by("-is_superuser", "-date_joined")
        if not users.exists():
            self.stdout.write(self.style.WARNING("No users found in the database."))
            self.stdout.write("Run: python manage.py setup_admin to create an admin account.\n")
            return

        self.stdout.write(self.style.SUCCESS(f"\nFound {users.count()} user(s) in the database:\n"))
        self.stdout.write(f"{'Username / Phone':<20} | {'Role':<15} | {'Superuser':<10} | {'Staff':<8}")
        self.stdout.write("-" * 65)

        for u in users:
            self.stdout.write(
                f"{u.username:<20} | {u.role:<15} | {str(u.is_superuser):<10} | {str(u.is_staff):<8}"
            )

        self.stdout.write("\n💡 Note: Passwords are encrypted for security and cannot be viewed.")
        self.stdout.write("To set or reset any user's password, run:")
        self.stdout.write("   python manage.py changepassword <USERNAME>\n")
