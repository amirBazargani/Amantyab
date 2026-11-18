from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.tokens import generate_verification_token, verify_token
from catalog.models import Category, Item
from core.models import NotificationLog

User = get_user_model()


class AccountsAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="StrongPassword123!",
            first_name="علی",
            last_name="محمدی",
            phone="09121112233",
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
                "phone": "09123456789",
                "first_name": "سارا",
                "last_name": "احمدی",
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        # Verify user is logged in
        new_user = response.context["user"]
        self.assertTrue(new_user.is_authenticated)
        self.assertEqual(new_user.username, "newuser")
        self.assertEqual(new_user.phone, "09123456789")

        # Verify NotificationLog rows (1 email, 1 sms)
        logs = NotificationLog.objects.filter(user=new_user, event="signup_confirmation")
        self.assertEqual(logs.count(), 2)
        email_log = logs.get(channel="email")
        sms_log = logs.get(channel="sms")
        self.assertEqual(email_log.status, "sent")
        self.assertEqual(sms_log.status, "sent")
        self.assertEqual(sms_log.recipient, "09123456789")

    def test_signup_missing_phone_shows_error(self):
        signup_url = reverse("accounts:signup")
        response = self.client.post(
            signup_url,
            {
                "username": "nophoneuser",
                "email": "nophone@example.com",
                "phone": "",
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "وارد کردن شماره موبایل الزامی است")
        self.assertFalse(User.objects.filter(username="nophoneuser").exists())

    def test_signup_invalid_phone_shows_error(self):
        signup_url = reverse("accounts:signup")
        response = self.client.post(
            signup_url,
            {
                "username": "badphoneuser",
                "email": "badphone@example.com",
                "phone": "08123456789",  # Does not start with 09
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "شماره موبایل نامعتبر است")
        self.assertFalse(User.objects.filter(username="badphoneuser").exists())

    def test_signup_phone_persian_digits_normalization(self):
        signup_url = reverse("accounts:signup")
        response = self.client.post(
            signup_url,
            {
                "username": "persianphone",
                "email": "persianphone@example.com",
                "phone": "۰۹۱۲۹۸۷۶۵۴۳",
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created_user = User.objects.get(username="persianphone")
        self.assertEqual(created_user.phone, "09129876543")

    def test_signup_notification_failure_does_not_stop_signup(self):
        signup_url = reverse("accounts:signup")
        # Simulate SMS backend failure
        with patch("core.sms.ConsoleBackend.send_sms", side_effect=RuntimeError("SMS Provider Unavailable")):
            response = self.client.post(
                signup_url,
                {
                    "username": "robustuser",
                    "email": "robust@example.com",
                    "phone": "09191112233",
                    "password1": "SecurePass1234!",
                    "password2": "SecurePass1234!",
                },
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        robust_user = User.objects.get(username="robustuser")
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(response.context["user"].username, "robustuser")

        # Verify SMS log captured the failure while email succeeded
        sms_log = NotificationLog.objects.get(user=robust_user, channel="sms")
        self.assertEqual(sms_log.status, "failed")
        self.assertIn("SMS Provider Unavailable", sms_log.error)

        email_log = NotificationLog.objects.get(user=robust_user, channel="email")
        self.assertEqual(email_log.status, "sent")

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

    def test_profile_edit_invalid_phone_shows_error(self):
        self.client.login(username="testuser", password="StrongPassword123!")
        profile_url = reverse("accounts:profile")
        response = self.client.post(
            profile_url,
            {
                "phone": "invalid_phone",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "شماره موبایل نامعتبر است")

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


class SessionManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sessionuser",
            email="sessionuser@example.com",
            password="StrongPassword123!",
            first_name="مهدی",
            phone="09124445566",
        )

    def test_session_settings_configured(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")
        self.assertEqual(settings.SESSION_COOKIE_AGE, 1209600)  # 2 weeks
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_login_remember_me_checked_uses_default_cookie_age(self):
        login_url = reverse("accounts:login")
        response = self.client.post(
            login_url,
            {
                "username": "sessionuser",
                "password": "StrongPassword123!",
                "remember_me": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)

        session = self.client.session
        # Should NOT expire at browser close
        self.assertFalse(session.get_expire_at_browser_close())
        # Age should be 2 weeks (1209600 seconds)
        self.assertEqual(session.get_expiry_age(), 1209600)

    def test_login_remember_me_unchecked_expires_at_browser_close(self):
        login_url = reverse("accounts:login")
        response = self.client.post(
            login_url,
            {
                "username": "sessionuser",
                "password": "StrongPassword123!",
                # remember_me is omitted / unchecked
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)

        session = self.client.session
        # Must expire at browser close
        self.assertTrue(session.get_expire_at_browser_close())

    def test_logout_clears_session(self):
        login_url = reverse("accounts:login")
        self.client.post(
            login_url,
            {
                "username": "sessionuser",
                "password": "StrongPassword123!",
                "remember_me": "on",
            },
        )
        # Store arbitrary data in session
        session = self.client.session
        session["catalog_search_filters"] = {"q": "دریل"}
        session.save()

        logout_url = reverse("accounts:logout")
        response = self.client.post(logout_url, follow=True)
        self.assertEqual(response.status_code, 200)

        # After logout, session should be flushed
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("catalog_search_filters", self.client.session)


class AccountsLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="loguser",
            email="loguser@example.com",
            password="StrongPassword123!",
            first_name="محمد",
            last_name="رضایی",
            phone="09121234567",
        )

    def test_login_success_logs_to_security(self):
        login_url = reverse("accounts:login")
        with self.assertLogs("amanatyab.security", level="INFO") as cm:
            response = self.client.post(
                login_url,
                {"username": "loguser", "password": "StrongPassword123!"},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("Login successful: user_id=" in msg and "username=loguser" in msg for msg in cm.output),
            f"Expected login success log in {cm.output}",
        )

    def test_login_failure_logs_to_security(self):
        login_url = reverse("accounts:login")
        with self.assertLogs("amanatyab.security", level="WARNING") as cm:
            response = self.client.post(
                login_url,
                {"username": "loguser", "password": "WrongPassword!"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("Login failed: username=loguser" in msg for msg in cm.output),
            f"Expected login failure log in {cm.output}",
        )

    def test_signup_logs_to_accounts(self):
        signup_url = reverse("accounts:signup")
        with self.assertLogs("amanatyab.accounts", level="INFO") as cm:
            response = self.client.post(
                signup_url,
                {
                    "username": "newlogger",
                    "email": "newlogger@example.com",
                    "phone": "09129998877",
                    "first_name": "احمد",
                    "last_name": "کرمی",
                    "password1": "SecurePass1234!",
                    "password2": "SecurePass1234!",
                },
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("New user registered: user_id=" in msg and "username=newlogger" in msg for msg in cm.output),
            f"Expected signup log in {cm.output}",
        )

    def test_logout_and_profile_edit_log_to_accounts(self):
        self.client.force_login(self.user)
        # 1. Profile edit log
        with self.assertLogs("amanatyab.accounts", level="INFO") as cm:
            resp = self.client.post(
                reverse("accounts:profile"),
                {
                    "first_name": "محمدعلی",
                    "last_name": "رضایی",
                    "phone": "09121234567",
                    "city": "تهران",
                    "neighborhood": "سعادت‌آباد",
                    "bio": "به‌روزرسانی بیوگرافی",
                },
                follow=True,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Profile updated: user_id=" in msg for msg in cm.output),
            f"Expected profile update log in {cm.output}",
        )

        # 2. Logout log
        with self.assertLogs("amanatyab.accounts", level="INFO") as cm_logout:
            resp_logout = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertEqual(resp_logout.status_code, 200)
        self.assertTrue(
            any("User logged out: user_id=" in msg for msg in cm_logout.output),
            f"Expected logout log in {cm_logout.output}",
        )


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="verifyuser",
            email="verifyuser@example.com",
            password="StrongPassword123!",
            phone="09123456789",
            is_email_verified=False,
        )

    def test_generate_and_verify_token_success(self):
        token = generate_verification_token(self.user)
        user, err = verify_token(token)
        self.assertIsNone(err)
        self.assertEqual(user, self.user)

    def test_verify_token_expired(self):
        token = generate_verification_token(self.user)
        user, err = verify_token(token, max_age=-1)
        self.assertIsNone(user)
        self.assertEqual(err, "expired")

    def test_verify_token_invalid_or_tampered(self):
        token = generate_verification_token(self.user) + "tampered"
        user, err = verify_token(token)
        self.assertIsNone(user)
        self.assertEqual(err, "invalid")

    def test_signup_email_contains_verification_link_and_sms_is_plain(self):
        signup_url = reverse("accounts:signup")
        res = self.client.post(
            signup_url,
            {
                "username": "emailcheckuser",
                "email": "emailcheck@example.com",
                "phone": "09121234567",
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        new_user = User.objects.get(username="emailcheckuser")
        self.assertFalse(new_user.is_email_verified)

        email_log = NotificationLog.objects.get(user=new_user, channel="email", event="signup_confirmation")
        sms_log = NotificationLog.objects.get(user=new_user, channel="sms", event="signup_confirmation")

        self.assertIn("verify-email", email_log.body)
        self.assertNotIn("verify-email", sms_log.body)

    def test_verify_email_view_success(self):
        token = generate_verification_token(self.user)
        url = reverse("accounts:verify_email", kwargs={"token": token})
        res = self.client.get(url, follow=True)
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_verify_email_view_expired_link(self):
        token = generate_verification_token(self.user)
        with patch("accounts.views.verify_token", return_value=(None, "expired")):
            url = reverse("accounts:verify_email", kwargs={"token": token})
            res = self.client.get(url)
            self.assertEqual(res.status_code, 400)
            self.assertContains(res, "لینک تایید منقضی شده است", status_code=400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_verify_email_view_invalid_link(self):
        url = reverse("accounts:verify_email", kwargs={"token": "bad-token-xyz"})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 400)
        self.assertContains(res, "لینک نامعتبر است", status_code=400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_resend_verification_view(self):
        self.client.force_login(self.user)
        url = reverse("accounts:resend_verification")

        # GET request renders verify_sent page
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertTemplateUsed(res_get, "accounts/verify_sent.html")

        # POST request sends verification email
        res_post = self.client.post(url)
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify-email", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_verified_required_blocks_unverified_user(self):
        self.client.force_login(self.user)

        res_item = self.client.get(reverse("catalog:item_create"), follow=True)
        self.assertRedirects(res_item, reverse("accounts:profile"))
        self.assertContains(res_item, "ابتدا باید آدرس ایمیل خود را تایید کنید")

        self.user.is_email_verified = True
        self.user.save()
        res_item_verified = self.client.get(reverse("catalog:item_create"))
        self.assertEqual(res_item_verified.status_code, 200)



