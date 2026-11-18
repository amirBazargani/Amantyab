from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tokens import generate_verification_token, verify_token

User = get_user_model()


class EmailVerificationTokenServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tokenuser",
            email="tokenuser@example.com",
            password="StrongPassword123!",
            phone="09123456789",
        )

    def test_generate_and_verify_token_success(self):
        token = generate_verification_token(self.user)
        self.assertIsInstance(token, str)
        user, err = verify_token(token)
        self.assertIsNone(err)
        self.assertEqual(user, self.user)

    def test_verify_token_expired(self):
        token = generate_verification_token(self.user)
        # Using negative max_age simulates expired token
        user, err = verify_token(token, max_age=-1)
        self.assertIsNone(user)
        self.assertEqual(err, "expired")

    def test_verify_token_tampered(self):
        token = generate_verification_token(self.user)
        tampered_token = token + "xyz"
        user, err = verify_token(tampered_token)
        self.assertIsNone(user)
        self.assertEqual(err, "invalid")

    def test_verify_token_nonexistent_user(self):
        token = generate_verification_token(self.user)
        # Delete user before verification
        self.user.delete()
        user, err = verify_token(token)
        self.assertIsNone(user)
        self.assertEqual(err, "user_not_found")
