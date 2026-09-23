from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Address, CustomerProfile

User = get_user_model()


class CustomerRegistrationTests(TestCase):
    def test_registration_creates_customer_user_and_profile(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Alice",
                "last_name": "Fernandes",
                "phone_number": "9876543210",
                "password1": "S3curePass!123",
                "password2": "S3curePass!123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="9876543210")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.first_name, "Alice")
        profile = CustomerProfile.objects.get(user=user)
        self.assertEqual(profile.phone_number, "9876543210")

    def test_registration_has_no_username_or_email_fields(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertNotContains(response, 'name="username"')
        self.assertNotContains(response, 'name="email"')

    def test_duplicate_phone_number_rejected(self):
        User.objects.create_user(username="9876500000", password="x")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Bob",
                "last_name": "",
                "phone_number": "9876500000",
                "password1": "S3curePass!123",
                "password2": "S3curePass!123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="9876500000").count(), 1)

    def test_invalid_phone_number_rejected(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Carl",
                "last_name": "",
                "phone_number": "abc123",
                "password1": "S3curePass!123",
                "password2": "S3curePass!123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(first_name="Carl").exists())


class PhoneLoginTests(TestCase):
    def setUp(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Dana",
                "last_name": "D",
                "phone_number": "9876511111",
                "password1": "S3curePass!123",
                "password2": "S3curePass!123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.client.logout()

    def test_customer_can_login_with_phone_number(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "9876511111", "password": "S3curePass!123"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_rejected(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "9876511111", "password": "WrongPassword!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "check your mobile number")

    def test_farmer_can_still_login_with_username(self):
        User.objects.create_user(
            username="farmadmin", password="AdminPass!123",
            role=User.Role.FARMER, is_staff=True,
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "farmadmin", "password": "AdminPass!123"},
        )
        self.assertEqual(response.status_code, 302)


class RoleAndAuthorizationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="9000000000", password="pw12345!"
        )
        CustomerProfile.objects.create(user=self.customer, phone_number="9000000000")

        self.other_customer = User.objects.create_user(
            username="9000000001", password="pw12345!"
        )
        CustomerProfile.objects.create(user=self.other_customer, phone_number="9000000001")

        self.farmer = User.objects.create_user(
            username="farmer", password="pw12345!",
            role=User.Role.FARMER, is_staff=True,
        )

    def test_default_role_is_customer(self):
        self.assertEqual(self.customer.role, User.Role.CUSTOMER)
        self.assertFalse(self.customer.is_farmer)

    def test_farmer_role_flag(self):
        self.assertTrue(self.farmer.is_farmer)

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response.url)

    def test_farmer_redirected_away_from_customer_profile_page(self):
        self.client.login(username="farmer", password="pw12345!")
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, reverse("farmer_orders:dashboard"))

    def test_customer_cannot_access_another_customers_address(self):
        address = Address.objects.create(
            customer=self.other_customer,
            full_name="Dave D",
            phone_number="9000000001",
            line1="12 Farm Lane",
            city="Pune",
            state="MH",
            postal_code="411001",
        )
        self.client.login(username="9000000000", password="pw12345!")
        response = self.client.get(
            reverse("accounts:address_edit", args=[address.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_customer_can_manage_own_address(self):
        self.client.login(username="9000000000", password="pw12345!")
        response = self.client.post(
            reverse("accounts:address_create"),
            {
                "label": "Home",
                "full_name": "Carol C",
                "phone_number": "9000000000",
                "line1": "1 Farm Lane",
                "line2": "",
                "city": "Pune",
                "state": "MH",
                "postal_code": "411001",
                "landmark": "",
                "is_default": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Address.objects.filter(customer=self.customer).exists())

    def test_only_one_default_address_per_customer(self):
        Address.objects.create(
            customer=self.customer, full_name="A", phone_number="9000000000",
            line1="L1", city="Pune", state="MH", postal_code="411001",
            is_default=True,
        )
        Address.objects.create(
            customer=self.customer, full_name="B", phone_number="9000000000",
            line1="L2", city="Pune", state="MH", postal_code="411002",
            is_default=True,
        )
        self.assertEqual(
            Address.objects.filter(customer=self.customer, is_default=True).count(), 1
        )


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_health_check(self):
        response = self.client.get(reverse("health_check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")


class FrictionlessAuthAndSimplifiedAddressTests(TestCase):
    def test_customer_registration_without_password(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Rohan",
                "phone_number": "9822001122",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="9822001122")
        self.assertEqual(user.first_name, "Rohan")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.has_usable_password())

    def test_customer_login_without_password(self):
        user = User.objects.create_user(
            username="9822334455",
            first_name="Pooja",
            role=User.Role.CUSTOMER,
        )
        user.set_unusable_password()
        user.save()
        CustomerProfile.objects.create(user=user, phone_number="9822334455")

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "9822334455"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pooja")

    def test_simplified_5_field_address_with_next_redirect(self):
        user = User.objects.create_user(
            username="9822556677",
            first_name="Amit",
            role=User.Role.CUSTOMER,
        )
        user.set_unusable_password()
        user.save()
        CustomerProfile.objects.create(user=user, phone_number="9822556677")
        self.client.force_login(user)

        checkout_url = reverse("orders:checkout")
        response = self.client.post(
            f"{reverse('accounts:address_create')}?next={checkout_url}",
            {
                "building_name": "Gokuldham Society",
                "flat_wing": "Flat 302, B Wing",
                "area_locality": "Powai",
                "city": "Mumbai",
                "postal_code": "400076",
                "next": checkout_url,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, checkout_url)

        address = Address.objects.filter(customer=user).first()
        self.assertIsNotNone(address)
        self.assertEqual(address.line1, "Flat 302, B Wing")
        self.assertEqual(address.line2, "Gokuldham Society")
        self.assertEqual(address.landmark, "Powai")
        self.assertEqual(address.city, "Mumbai")
        self.assertEqual(address.postal_code, "400076")
        self.assertEqual(address.full_name, "Amit")
        self.assertEqual(address.phone_number, "9822556677")

