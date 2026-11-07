from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Category, Item, ItemImage

User = get_user_model()


class CatalogViewsTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="testowner",
            email="owner@example.com",
            password="StrongPassword123!",
            first_name="مالک",
            last_name="تست",
            phone="09121111111",
            city="تهران",
            neighborhood="ونک",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="StrongPassword123!",
            phone="09122222222",
            city="تبریز",
        )
        self.staff_user = User.objects.create_user(
            username="adminuser",
            email="admin@example.com",
            password="StrongPassword123!",
            phone="09123333333",
            is_staff=True,
        )

        self.cat_tools = Category.objects.create(name="ابزارآلات", slug="tools")
        self.cat_camping = Category.objects.create(name="کمپینگ", slug="camping")

        # Active item 1 (Tools, Tehran, daily 50000)
        self.item_drill = Item.objects.create(
            owner=self.owner,
            category=self.cat_tools,
            title="دریل برقی چکشی رونیکس",
            description="دریل قدرتمند با ست کامل مته‌ها",
            brand="Ronix",
            condition=Item.Condition.LIKE_NEW,
            hourly_price=Decimal("15000"),
            daily_price=Decimal("50000"),
            deposit_amount=Decimal("200000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=True,
            is_active=True,
        )

        # Active item 2 (Camping, Tehran, daily 80000)
        self.item_tent = Item.objects.create(
            owner=self.owner,
            category=self.cat_camping,
            title="چادر مسافرتی ۴ نفره ضدآب",
            description="چادر کلمن مناسب کوهنوردی و سفر خانوادگی",
            brand="Coleman",
            condition=Item.Condition.GOOD,
            hourly_price=None,
            daily_price=Decimal("80000"),
            deposit_amount=Decimal("300000"),
            city="تهران",
            neighborhood="پونک",
            allow_pickup=True,
            allow_courier=False,
            is_active=True,
        )

        # Active item 3 (Tools, Isfahan, daily 120000)
        self.item_saw = Item.objects.create(
            owner=self.other_user,
            category=self.cat_tools,
            title="اره فارسی بر بوش",
            description="اره صنعتی دقیق برای نجاری",
            brand="Bosch",
            condition=Item.Condition.NEW,
            hourly_price=Decimal("25000"),
            daily_price=Decimal("120000"),
            deposit_amount=Decimal("500000"),
            city="اصفهان",
            neighborhood="مرداویج",
            allow_pickup=True,
            allow_courier=True,
            is_active=True,
        )

        # Inactive item (should never appear in search or public list)
        self.inactive_item = Item.objects.create(
            owner=self.owner,
            category=self.cat_tools,
            title="بتن کن هیلتی غیرفعال",
            description="دستگاه موقتا برای تعمیر از دسترس خارج است",
            brand="Hilti",
            condition=Item.Condition.FAIR,
            daily_price=Decimal("200000"),
            deposit_amount=Decimal("1000000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=False,
            is_active=False,
        )

        # Attach image to item_drill
        small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04"
            b"\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44"
            b"\x01\x00\x3b"
        )
        self.test_img = SimpleUploadedFile("drill.gif", small_gif, content_type="image/gif")
        self.item_image = ItemImage.objects.create(
            item=self.item_drill,
            image=self.test_img,
            is_primary=True,
            order=0,
        )

    def test_item_list_shows_only_active_items(self):
        """Active items must be visible and inactive items must be excluded."""
        response = self.client.get(reverse("catalog:item_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item_drill.title)
        self.assertContains(response, self.item_tent.title)
        self.assertContains(response, self.item_saw.title)
        self.assertNotContains(response, self.inactive_item.title)
        self.assertEqual(response.context["total_count"], 3)

    def test_item_list_filter_by_query_title_description_brand(self):
        """Filtering with ?q matches title, description, and brand."""
        # Query title
        res1 = self.client.get(reverse("catalog:item_list"), {"q": "دریل"})
        self.assertContains(res1, self.item_drill.title)
        self.assertNotContains(res1, self.item_tent.title)
        self.assertNotContains(res1, self.item_saw.title)

        # Query description
        res2 = self.client.get(reverse("catalog:item_list"), {"q": "کوهنوردی"})
        self.assertContains(res2, self.item_tent.title)
        self.assertNotContains(res2, self.item_drill.title)

        # Query brand
        res3 = self.client.get(reverse("catalog:item_list"), {"q": "Bosch"})
        self.assertContains(res3, self.item_saw.title)
        self.assertNotContains(res3, self.item_drill.title)

    def test_item_list_filter_by_category_slug_and_id(self):
        """Filtering by category works with both slug and numeric ID."""
        # Category slug
        res_slug = self.client.get(reverse("catalog:item_list"), {"category": "camping"})
        self.assertEqual(res_slug.context["total_count"], 1)
        self.assertContains(res_slug, self.item_tent.title)
        self.assertNotContains(res_slug, self.item_drill.title)

        # Category ID
        res_id = self.client.get(reverse("catalog:item_list"), {"category": str(self.cat_tools.id)})
        self.assertEqual(res_id.context["total_count"], 2)
        self.assertContains(res_id, self.item_drill.title)
        self.assertContains(res_id, self.item_saw.title)
        self.assertNotContains(res_id, self.item_tent.title)

    def test_item_list_filter_by_city(self):
        """Filtering by city returns only items located in that city."""
        res_tehran = self.client.get(reverse("catalog:item_list"), {"city": "تهران"})
        self.assertEqual(res_tehran.context["total_count"], 2)
        self.assertContains(res_tehran, self.item_drill.title)
        self.assertContains(res_tehran, self.item_tent.title)
        self.assertNotContains(res_tehran, self.item_saw.title)

        res_isfahan = self.client.get(reverse("catalog:item_list"), {"city": "اصفهان"})
        self.assertEqual(res_isfahan.context["total_count"], 1)
        self.assertContains(res_isfahan, self.item_saw.title)

    def test_item_list_filter_by_max_price(self):
        """Filtering by max_price filters daily_price <= max_price, and handles invalid gracefully."""
        res_price = self.client.get(reverse("catalog:item_list"), {"max_price": "60000"})
        self.assertEqual(res_price.context["total_count"], 1)
        self.assertContains(res_price, self.item_drill.title)
        self.assertNotContains(res_price, self.item_tent.title)
        self.assertNotContains(res_price, self.item_saw.title)

        # Invalid price does not crash
        res_invalid = self.client.get(reverse("catalog:item_list"), {"max_price": "invalid_number"})
        self.assertEqual(res_invalid.status_code, 200)
        self.assertEqual(res_invalid.context["total_count"], 3)

    def test_item_list_combined_filters(self):
        """Filters combine correctly using AND logic."""
        res = self.client.get(
            reverse("catalog:item_list"),
            {
                "q": "دریل",
                "category": "tools",
                "city": "تهران",
                "max_price": "100000",
            },
        )
        self.assertEqual(res.context["total_count"], 1)
        self.assertContains(res, self.item_drill.title)

        # Same filters but with incompatible city
        res_mismatch = self.client.get(
            reverse("catalog:item_list"),
            {
                "q": "دریل",
                "category": "tools",
                "city": "شیراز",
            },
        )
        self.assertEqual(res_mismatch.context["total_count"], 0)
        self.assertContains(res_mismatch, "کالایی یافت نشد")

    def test_item_detail_shows_complete_information(self):
        """Detail page shows images, prices, deposit, owner, and delivery options."""
        response = self.client.get(reverse("catalog:item_detail", args=[self.item_drill.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item_drill.title)
        self.assertContains(response, "50000")  # daily price
        self.assertContains(response, "15000")  # hourly price
        self.assertContains(response, "200000")  # deposit amount
        self.assertContains(response, "تحویل حضوری")
        self.assertContains(response, "ارسال با پیک")
        self.assertContains(response, self.owner.get_full_name())
        self.assertContains(response, "ونک")
        self.assertContains(response, "Ronix")
        self.assertEqual(response.context["primary_image"], self.item_image)

    def test_inactive_item_hidden_from_public_and_visible_to_owner_staff(self):
        """Inactive item raises 404 for anonymous/other users, but is viewable by owner and staff."""
        # Anonymous user gets 404
        anon_res = self.client.get(reverse("catalog:item_detail", args=[self.inactive_item.pk]))
        self.assertEqual(anon_res.status_code, 404)

        # Other user gets 404
        self.client.force_login(self.other_user)
        other_res = self.client.get(reverse("catalog:item_detail", args=[self.inactive_item.pk]))
        self.assertEqual(other_res.status_code, 404)

        # Owner gets 200 with notice
        self.client.force_login(self.owner)
        owner_res = self.client.get(reverse("catalog:item_detail", args=[self.inactive_item.pk]))
        self.assertEqual(owner_res.status_code, 200)
        self.assertContains(owner_res, "غیرفعال")

        # Staff gets 200
        self.client.force_login(self.staff_user)
        staff_res = self.client.get(reverse("catalog:item_detail", args=[self.inactive_item.pk]))
        self.assertEqual(staff_res.status_code, 200)


class ItemGeoFieldsTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="geouser",
            email="geo@example.com",
            password="StrongPassword123!",
            phone="09124444444",
        )
        self.category = Category.objects.create(name="ابزار", slug="tools-geo")

    def test_lat_without_lng_raises_integrity_error(self):
        """Item with latitude set but longitude None violates DB constraint."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Item.objects.create(
                owner=self.owner,
                category=self.category,
                title="Invalid Lat Only",
                description="desc",
                condition=Item.Condition.NEW,
                daily_price=Decimal("50000"),
                city="تهران",
                allow_pickup=True,
                latitude=Decimal("35.6892"),
                longitude=None,
            )

    def test_latitude_120_fails_full_clean(self):
        """Item with latitude > 90 fails full_clean() validation."""
        from django.core.exceptions import ValidationError

        item = Item(
            owner=self.owner,
            category=self.category,
            title="Invalid Lat Value",
            description="desc",
            condition=Item.Condition.NEW,
            daily_price=Decimal("50000"),
            city="تهران",
            allow_pickup=True,
            latitude=Decimal("120.0"),
            longitude=Decimal("51.3890"),
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_valid_coordinates_and_address_text_persist(self):
        """Item with valid coordinates and address text saves and cleans properly."""
        item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="Valid Coordinates Item",
            description="desc",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("50000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            address_text="میدان ونک، خیابان ملاصدرا",
            latitude=Decimal("35.757500"),
            longitude=Decimal("51.410000"),
        )
        item.full_clean()
        self.assertEqual(item.address_text, "میدان ونک، خیابان ملاصدرا")
        self.assertEqual(item.latitude, Decimal("35.757500"))
        self.assertEqual(item.longitude, Decimal("51.410000"))

