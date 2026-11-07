from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Item

User = get_user_model()


class AccountsAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="StrongPassword123!",
            first_name="علی",
            last_name="محمدی",
            city="تهران",
            neighborhood="ونک",
            bio="علاقه‌مند به ابزار و تجهیزات نجاری",
        )

    def test_signup_success_and_auto_login(self):
        signup_url = reverse("accounts:signup")
        response = self.client.post(
            signup_url,
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "first_name": "سارا",
                "last_name": "احمدی",
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        # Verify user is logged in
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(response.context["user"].username, "newuser")
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_login_wrong_password_shows_error(self):
        login_url = reverse("accounts:login")
        response = self.client.post(
            login_url,
            {
                "username": "testuser",
                "password": "WrongPassword!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام کاربری یا رمز عبور")
        self.assertFalse(response.context["user"].is_authenticated)

    def test_login_success(self):
        login_url = reverse("accounts:login")
        response = self.client.post(
            login_url,
            {
                "username": "testuser",
                "password": "StrongPassword123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(response.context["user"].username, "testuser")

    def test_logout(self):
        self.client.login(username="testuser", password="StrongPassword123!")
        logout_url = reverse("accounts:logout")
        response = self.client.post(logout_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_anonymous_redirect_from_profile_edit(self):
        profile_url = reverse("accounts:profile")
        response = self.client.get(profile_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse("accounts:login")
        self.assertIn(login_url, response.url)

    def test_profile_edit_saves(self):
        self.client.login(username="testuser", password="StrongPassword123!")
        profile_url = reverse("accounts:profile")
        response = self.client.post(
            profile_url,
            {
                "first_name": "علیرضا",
                "last_name": "محمدی‌نیا",
                "phone": "09129998877",
                "city": "اصفهان",
                "neighborhood": "مرداویج",
                "bio": "بیوگرافی جدید ویرایش شده",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "علیرضا")
        self.assertEqual(self.user.last_name, "محمدی‌نیا")
        self.assertEqual(self.user.city, "اصفهان")
        self.assertEqual(self.user.neighborhood, "مرداویج")
        self.assertEqual(self.user.phone, "09129998877")
        self.assertEqual(self.user.bio, "بیوگرافی جدید ویرایش شده")

    def test_public_profile_shows_name_city_and_items(self):
        category = Category.objects.create(name="ابزار برقی", slug="power-tools")
        Item.objects.create(
            owner=self.user,
            category=category,
            title="دریل چکشی رونیکس",
            description="دریل چکشی قدرتمند برای سوراخکاری بتن",
            condition=Item.Condition.LIKE_NEW,
            daily_price=Decimal("150000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=True,
            is_active=True,
        )
        Item.objects.create(
            owner=self.user,
            category=category,
            title="کالای غیرفعال",
            description="این کالا نباید در پروفایل عمومی نشان داده شود",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("100000"),
            deposit_amount=Decimal("200000"),
            city="تهران",
            allow_pickup=True,
            is_active=False,
        )

        public_profile_url = reverse(
            "accounts:public_profile",
            kwargs={"username": self.user.username},
        )
        response = self.client.get(public_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "علی")
        self.assertContains(response, "تهران")
        self.assertContains(response, "دریل چکشی رونیکس")
        self.assertNotContains(response, "کالای غیرفعال")
