from decimal import Decimal
from urllib.parse import quote
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from catalog.models import Category, Item
from core.cookies import (
    LAST_CITY_COOKIE,
    RECENT_ITEMS_COOKIE,
    RECENT_ITEMS_SALT,
    add_recent_item_id,
    get_last_city,
    get_recent_item_ids,
    set_last_city,
)
from core.middleware import RequestLogMiddleware
from core.notifications import mask_email, mask_phone, notify

User = get_user_model()


class CookieHelperTests(TestCase):
    """Unit tests for cookie helper functions in core.cookies."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_get_recent_item_ids_empty_when_no_cookie(self):
        request = self.factory.get("/")
        ids = get_recent_item_ids(request)
        self.assertEqual(ids, [])

    def test_add_recent_item_id_and_retrieve(self):
        request = self.factory.get("/")
        response = HttpResponse()
        add_recent_item_id(response, request, 101)

        self.assertIn(RECENT_ITEMS_COOKIE, response.cookies)
        cookie = response.cookies[RECENT_ITEMS_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["max-age"], 7 * 24 * 60 * 60)

        # Simulate request containing this signed cookie
        request.COOKIES[RECENT_ITEMS_COOKIE] = cookie.value
        ids = get_recent_item_ids(request)
        self.assertEqual(ids, [101])

    def test_add_recent_item_deduplication_and_order(self):
        request = self.factory.get("/")
        response = HttpResponse()

        # Add 1, 2, 3
        for pk in [1, 2, 3]:
            add_recent_item_id(response, request, pk)
            request.COOKIES[RECENT_ITEMS_COOKIE] = response.cookies[RECENT_ITEMS_COOKIE].value

        ids = get_recent_item_ids(request)
        self.assertEqual(ids, [3, 2, 1])

        # Add 2 again -> should move 2 to front without duplication
        add_recent_item_id(response, request, 2)
        request.COOKIES[RECENT_ITEMS_COOKIE] = response.cookies[RECENT_ITEMS_COOKIE].value
        ids = get_recent_item_ids(request)
        self.assertEqual(ids, [2, 3, 1])

    def test_add_recent_item_max_count_cap(self):
        request = self.factory.get("/")
        response = HttpResponse()

        # Add 8 unique items (exceeds cap of 6)
        for pk in range(1, 9):
            add_recent_item_id(response, request, pk)
            request.COOKIES[RECENT_ITEMS_COOKIE] = response.cookies[RECENT_ITEMS_COOKIE].value

        ids = get_recent_item_ids(request)
        self.assertEqual(len(ids), 6)
        self.assertEqual(ids, [8, 7, 6, 5, 4, 3])

    def test_tampered_cookie_ignored_gracefully(self):
        request = self.factory.get("/")
        # Provide a tampered / invalid signed cookie
        request.COOKIES[RECENT_ITEMS_COOKIE] = "tampered_value:invalid_signature"

        ids = get_recent_item_ids(request)
        # Must return empty list without raising any exception or crashing
        self.assertEqual(ids, [])

    def test_last_city_cookie_get_and_set(self):
        request = self.factory.get("/")
        response = HttpResponse()

        set_last_city(response, "اصفهان")
        self.assertIn(LAST_CITY_COOKIE, response.cookies)
        cookie = response.cookies[LAST_CITY_COOKIE]
        self.assertEqual(cookie["max-age"], 7 * 24 * 60 * 60)

        request.COOKIES[LAST_CITY_COOKIE] = cookie.value
        city = get_last_city(request)
        self.assertEqual(city, "اصفهان")


class HomePageCookieViewTests(TestCase):
    """Integration tests for home page displaying recently viewed items and pre-selecting last city."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="home_owner",
            email="home_owner@example.com",
            password="StrongPassword123!",
            city="شیراز",
        )
        self.cat = Category.objects.create(name="ابزار", slug="tools")

        self.item1 = Item.objects.create(
            owner=self.owner,
            category=self.cat,
            title="دریل هیلتی",
            daily_price=Decimal("80000"),
            city="شیراز",
            is_active=True,
        )
        self.item2 = Item.objects.create(
            owner=self.owner,
            category=self.cat,
            title="نردبان تلسکوپی",
            daily_price=Decimal("45000"),
            city="تهران",
            is_active=True,
        )
        self.inactive_item = Item.objects.create(
            owner=self.owner,
            category=self.cat,
            title="اره برقی غیرفعال",
            daily_price=Decimal("60000"),
            city="تبریز",
            is_active=False,
        )

    def test_home_without_cookies(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "کالاهای اخیراً مشاهده‌شده")

    def test_home_with_recent_items_cookie(self):
        request = RequestFactory().get("/")
        resp = HttpResponse()
        for pk in [self.item1.pk, self.inactive_item.pk, self.item2.pk]:
            add_recent_item_id(resp, request, pk)
            request.COOKIES[RECENT_ITEMS_COOKIE] = resp.cookies[RECENT_ITEMS_COOKIE].value

        signed_cookie_val = resp.cookies[RECENT_ITEMS_COOKIE].value
        self.client.cookies[RECENT_ITEMS_COOKIE] = signed_cookie_val

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کالاهای اخیراً مشاهده‌شده")
        self.assertContains(response, "دریل هیلتی")
        self.assertContains(response, "نردبان تلسکوپی")
        # Inactive item must NOT be displayed
        self.assertNotContains(response, "اره برقی غیرفعال")

    def test_home_with_last_city_cookie(self):
        self.client.cookies[LAST_CITY_COOKIE] = quote("شیراز")
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        # City select option should have selected for شیراز
        self.assertContains(response, '<option value="شیراز" selected>شیراز</option>')
        self.assertContains(response, "شهر برگزیده شما بر اساس آخرین بازدید")

    def test_home_with_tampered_cookie_does_not_crash(self):
        self.client.cookies[RECENT_ITEMS_COOKIE] = "tampered:bad_signature"
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "کالاهای اخیراً مشاهده‌شده")


class RequestLogMiddlewareTests(TestCase):
    """Tests for RequestLogMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="loguser",
            email="loguser@example.com",
            phone="09121112233",
            password="password123",
        )

    def test_anonymous_request_logged(self):
        middleware = RequestLogMiddleware(lambda req: HttpResponse("OK", status=200))
        request = self.factory.get("/some/path/?page=1")
        request.user = AnonymousUser()

        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            response = middleware(request)
            self.assertEqual(response.status_code, 200)

        output = " ".join(cm.output)
        self.assertIn("GET /some/path/?page=1", output)
        self.assertIn("user=anonymous", output)
        self.assertIn("status=200", output)
        self.assertIn("duration=", output)

    def test_authenticated_request_logged(self):
        middleware = RequestLogMiddleware(lambda req: HttpResponse("OK", status=200))
        request = self.factory.post("/catalog/create/")
        request.user = self.user

        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            response = middleware(request)
            self.assertEqual(response.status_code, 200)

        output = " ".join(cm.output)
        self.assertIn("POST /catalog/create/", output)
        self.assertIn(f"user={self.user.pk}", output)
        self.assertIn("status=200", output)
        self.assertIn("duration=", output)

    def test_exception_in_view_logs_exception_and_raises(self):
        def failing_view(req):
            raise ValueError("Something broke")

        middleware = RequestLogMiddleware(failing_view)
        request = self.factory.get("/broken/")
        request.user = self.user

        with self.assertLogs("amanatyab.core", level="ERROR") as cm:
            with self.assertRaises(ValueError):
                middleware(request)

        output = " ".join(cm.output)
        self.assertIn("GET /broken/", output)
        self.assertIn(f"user={self.user.pk}", output)
        self.assertIn("status=500", output)

    def test_real_client_request_writes_to_log(self):
        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            response = self.client.get(reverse("core:home"))
            self.assertEqual(response.status_code, 200)

        output = " ".join(cm.output)
        self.assertIn("GET /", output)
        self.assertIn("status=200", output)


class NotificationLoggingTests(TestCase):
    """Tests for phone/email masking and notification logging behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="notifuser",
            email="notifuser@example.com",
            phone="09123456789",
            password="password123",
        )

    def test_mask_phone(self):
        self.assertEqual(mask_phone("09123456789"), "********789")
        self.assertEqual(mask_phone("123"), "123")
        self.assertEqual(mask_phone(""), "")
        self.assertEqual(mask_phone(None), "")

    def test_mask_email(self):
        self.assertEqual(mask_email("notifuser@example.com"), "@example.com")
        self.assertEqual(mask_email("someone@sub.domain.org"), "@sub.domain.org")
        self.assertEqual(mask_email(""), "")
        self.assertEqual(mask_email(None), "")
        self.assertEqual(mask_email("invalid_email"), "")

    def test_notify_logs_masked_recipients_and_never_logs_body(self):
        secret_content = "SECRET_SUPER_CONFIDENTIAL_TOKEN_12345"

        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            notify(self.user, "test_event", context={"secret": secret_content})

        output = " ".join(cm.output)

        # Must log attempts to amanatyab.core with event, channel, user id, status
        self.assertIn("event=test_event", output)
        self.assertIn("channel=email", output)
        self.assertIn("channel=sms", output)
        self.assertIn(f"user_id={self.user.pk}", output)
        self.assertIn("status=sent", output)

        # Phone numbers are masked (last 3 digits visible)
        self.assertIn("********789", output)
        self.assertNotIn("09123456789", output)

        # Emails show only the domain
        self.assertIn("@example.com", output)
        self.assertNotIn("notifuser@", output)

        # Message bodies are NEVER logged
        self.assertNotIn(secret_content, output)

    def test_notify_skipped_logging(self):
        user_no_contact = User.objects.create_user(
            username="nocontact",
            email="",
            phone="",
            password="password123",
        )
        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            notify(user_no_contact, "test_skip_event")

        output = " ".join(cm.output)
        self.assertIn("event=test_skip_event", output)
        self.assertIn("status=skipped", output)

