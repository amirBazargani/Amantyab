from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_with_phone_and_profile_fields(self):
        user = User.objects.create_user(
            username="modeluser",
            email="modeluser@example.com",
            password="StrongPassword123!",
            first_name="مهدی",
            last_name="عباسی",
            phone="09121234567",
            city="تهران",
            neighborhood="ونک",
            bio="کاربر علاقه‌مند به ابزار نجاری",
        )
        self.assertEqual(user.username, "modeluser")
        self.assertEqual(user.phone, "09121234567")
        self.assertEqual(user.city, "تهران")
        self.assertEqual(user.neighborhood, "ونک")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(str(user), "modeluser")

    def test_user_email_verified_flag(self):
        user = User.objects.create_user(
            username="verifieduser",
            email="verified@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )
        self.assertTrue(user.is_email_verified)
