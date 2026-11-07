from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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


