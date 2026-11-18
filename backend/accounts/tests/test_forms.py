from django.test import TestCase

from accounts.forms import (
    LoginForm,
    ProfileForm,
    SignUpForm,
    normalize_iranian_phone,
)


class AccountsFormsTests(TestCase):
    def test_normalize_iranian_phone(self):
        # Persian digits
        self.assertEqual(normalize_iranian_phone("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789")
        # Arabic digits
        self.assertEqual(normalize_iranian_phone("٠٩١٢٣٤٥٦٧٨٩"), "09123456789")
        # Spaces, dashes, parentheses
        self.assertEqual(normalize_iranian_phone("0912-345 6789"), "09123456789")
        self.assertEqual(normalize_iranian_phone("(0912) 345-6789"), "09123456789")
        # +98 prefix
        self.assertEqual(normalize_iranian_phone("+989123456789"), "09123456789")
        # 0098 prefix
        self.assertEqual(normalize_iranian_phone("00989123456789"), "09123456789")
        # 98 prefix without plus
        self.assertEqual(normalize_iranian_phone("989123456789"), "09123456789")
        # Empty/None
        self.assertEqual(normalize_iranian_phone(""), "")
        self.assertEqual(normalize_iranian_phone(None), "")

    def test_signup_form_valid(self):
        form_data = {
            "username": "formuser",
            "email": "formuser@example.com",
            "phone": "۰۹۱۲۳۴۵۶۷۸۹",
            "first_name": "سارا",
            "last_name": "احمدی",
            "password1": "SecurePass1234!",
            "password2": "SecurePass1234!",
        }
        form = SignUpForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "09123456789")

    def test_signup_form_invalid_phone(self):
        form_data = {
            "username": "formuser",
            "email": "formuser@example.com",
            "phone": "08123456789",  # Invalid prefix
            "password1": "SecurePass1234!",
            "password2": "SecurePass1234!",
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_signup_form_missing_phone(self):
        form_data = {
            "username": "formuser",
            "email": "formuser@example.com",
            "phone": "",
            "password1": "SecurePass1234!",
            "password2": "SecurePass1234!",
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_login_form_remember_me_field(self):
        form = LoginForm()
        self.assertIn("remember_me", form.fields)
        self.assertFalse(form.fields["remember_me"].required)

    def test_profile_form_valid_and_phone_normalization(self):
        form_data = {
            "first_name": "علی",
            "last_name": "رضایی",
            "phone": "۰۹۱۲۹۹۹۸۸۷۷",
            "city": "تهران",
            "neighborhood": "پونک",
            "bio": "درباره من",
        }
        form = ProfileForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "09129998877")
