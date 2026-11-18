from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.signing import Signer
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from catalog.models import Category, Item
from core.cookies import (
    LAST_CITY_COOKIE,
    RECENT_ITEMS_COOKIE,
    add_recent_item_id,
    get_last_city,
    get_recent_item_ids,
    set_last_city,
)

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
        self.assertEqual(ids, [])

    def test_tampered_cookie_altered_data_with_valid_length(self):
        request = self.factory.get("/")
        response = HttpResponse()
        add_recent_item_id(response, request, 42)
        valid_cookie = response.cookies[RECENT_ITEMS_COOKIE].value

        # Tamper one character
        tampered = valid_cookie[:-3] + "abc"
        request.COOKIES[RECENT_ITEMS_COOKIE] = tampered
        ids = get_recent_item_ids(request)
        self.assertEqual(ids, [])

    def test_tampered_cookie_bad_json_payload(self):
        request = self.factory.get("/")
        # Sign invalid JSON
        signer = Signer(salt=RECENT_ITEMS_COOKIE)
        bad_payload = signer.sign("not-a-json-list")
        request.COOKIES[RECENT_ITEMS_COOKIE] = bad_payload

        ids = get_recent_item_ids(request)
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
    """Integration tests for recent items and last city cookies in home view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="owner_home",
            email="owner_home@example.com",
            phone="09121112233",
            password="password123",
        )
        self.category = Category.objects.create(name="ابزار برقی", slug="power-tools")
        self.item1 = Item.objects.create(
            owner=self.user,
            category=self.category,
            title="دریل چکشی بوش",
            daily_price=Decimal("150000"),
            city="تهران",
            is_active=True,
        )
        self.item2 = Item.objects.create(
            owner=self.user,
            category=self.category,
            title="اره عمودبر رونیکس",
            daily_price=Decimal("120000"),
            city="اصفهان",
            is_active=True,
        )
        self.inactive_item = Item.objects.create(
            owner=self.user,
            category=self.category,
            title="کالای غیرفعال",
            daily_price=Decimal("100000"),
            city="تهران",
            is_active=False,
        )

    def test_home_page_without_cookie_has_no_recent_items(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["recent_items"]), [])

    def test_home_page_with_valid_recent_items_cookie(self):
        # Visit item1 then item2
        self.client.get(reverse("catalog:item_detail", kwargs={"pk": self.item1.pk}))
        self.client.get(reverse("catalog:item_detail", kwargs={"pk": self.item2.pk}))

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        recent_items = list(response.context["recent_items"])
        self.assertEqual(len(recent_items), 2)
        # Order should be most recently viewed first
        self.assertEqual(recent_items[0], self.item2)
        self.assertEqual(recent_items[1], self.item1)

    def test_home_page_with_tampered_cookie_renders_safely(self):
        self.client.cookies[RECENT_ITEMS_COOKIE] = "malicious_payload_fake_signature"
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["recent_items"]), [])

    def test_home_page_filters_out_inactive_recent_items(self):
        request = RequestFactory().get("/")
        response_dummy = HttpResponse()
        add_recent_item_id(response_dummy, request, self.inactive_item.pk)
        add_recent_item_id(response_dummy, request, self.item1.pk)

        cookie_val = response_dummy.cookies[RECENT_ITEMS_COOKIE].value
        self.client.cookies[RECENT_ITEMS_COOKIE] = cookie_val

        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        recent_items = list(response.context["recent_items"])
        self.assertEqual(recent_items, [self.item1])
        self.assertNotIn(self.inactive_item, recent_items)
