from decimal import Decimal
from urllib.parse import quote
from django.contrib.auth import get_user_model
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
