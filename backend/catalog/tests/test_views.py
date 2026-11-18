from decimal import Decimal
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.cookies import (
    LAST_CITY_COOKIE,
    RECENT_ITEMS_COOKIE,
    get_last_city,
    get_recent_item_ids,
)
from catalog.models import Category, Item, ItemImage

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

    def test_item_list_query_count_under_limit(self):
        """
        Verify that browsing item_list with 25 items executes at most 5 database queries,
        guaranteeing elimination of N+1 queries.
        """
        extra_items = [
            Item(
                owner=self.owner,
                category=self.cat_tools if i % 2 == 0 else self.cat_camping,
                title=f"کالای آزمایشی بهینه‌سازی {i}",
                description="توضیحات تست بهینه‌سازی کوئری",
                daily_price=Decimal("45000"),
                city="تهران",
                neighborhood="ونک",
                is_active=True,
            )
            for i in range(25)
        ]
        Item.objects.bulk_create(extra_items)
        created_items = list(Item.objects.filter(title__startswith="کالای آزمایشی بهینه‌سازی"))
        ItemImage.objects.bulk_create([
            ItemImage(item=item, image="items/dummy.jpg", is_primary=True)
            for item in created_items
        ])

        # Must execute <= 5 queries (categories, cities, items, images, and session if any)
        with self.assertNumQueries(4):
            response = self.client.get(reverse("catalog:item_list"))
            self.assertEqual(response.status_code, 200)
            self.assertGreaterEqual(response.context["total_count"], 25)

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




class ItemOwnerManagementTestCase(TestCase):
    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from rentals.models import Rental

        self.owner = User.objects.create_user(
            username="itemowner",
            email="itemowner@example.com",
            password="StrongPassword123!",
            first_name="فرهاد",
            last_name="رضایی",
            phone="09121112233",
            city="تهران",
            is_email_verified=True,
        )
        self.other_user = User.objects.create_user(
            username="otherrenter",
            email="renter@example.com",
            password="StrongPassword123!",
            first_name="سامان",
            phone="09129998877",
            city="تهران",
            is_email_verified=True,
        )
        self.category = Category.objects.create(name="ابزار برقی", slug="electric-tools")

        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="فرز سنگبری رونیکس",
            description="فرز سنگبری با قدرت بالا و صفحه برش سالم",
            brand="Ronix",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("80000"),
            deposit_amount=Decimal("300000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=True,
            is_active=True,
        )

        # Rental on the item
        now = timezone.now()
        self.rental = Rental.objects.create(
            item=self.item,
            renter=self.other_user,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=2),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            status=Rental.Status.HANDED_OVER,
            rent_amount=Decimal("160000"),
            deposit_amount=Decimal("300000"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("24000"),
            owner_payout=Decimal("136000"),
        )

        # Another item owned by self.owner without any rentals
        self.unused_item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="نردبان تلسکوپی آلومینیومی",
            description="نردبان تاشو ۴ متری بسیار سبک و مقاوم",
            condition=Item.Condition.NEW,
            daily_price=Decimal("45000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )

        self.small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04"
            b"\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
            b"\x02\x4c\x01\x00\x3b"
        )

    def test_my_items_requires_login(self):
        """Anonymous user cannot access my_items page and is redirected to login."""
        res = self.client.get(reverse("catalog:my_items"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("accounts:login"), res.url)

    def test_my_items_shows_owner_items_and_active_rental(self):
        """Owner can view their own items and the remaining rental time + renter details."""
        self.client.force_login(self.owner)
        res = self.client.get(reverse("catalog:my_items"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "مدیریت کالاهای من")
        self.assertContains(res, "فرز سنگبری رونیکس")
        self.assertContains(res, "نردبان تلسکوپی آلومینیومی")
        # Should show renter information and active rental status
        self.assertContains(res, "هم‌اکنون در دست اجاره")
        self.assertContains(res, "سامان")
        self.assertContains(res, "مانده")

    def test_item_create_view_get(self):
        """Owner can load the item creation form."""
        self.client.force_login(self.owner)
        res = self.client.get(reverse("catalog:item_create"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ثبت کالای جدید برای امانت")

    def test_item_create_view_post_with_image(self):
        """Owner can create an item with uploaded image and proper validation."""
        self.client.force_login(self.owner)
        uploaded_image = SimpleUploadedFile("tool.gif", self.small_gif, content_type="image/gif")

        post_data = {
            "category": self.category.pk,
            "title": "اره فارسی‌بر ماکیتا",
            "description": "اره با تیغه الماسه مناسب برش چوب",
            "brand": "Makita",
            "condition": Item.Condition.LIKE_NEW,
            "daily_price": "75000",
            "deposit_amount": "250000",
            "city": "تهران",
            "neighborhood": "پونک",
            "allow_pickup": "on",
            "address_text": "پونک، بلوار میرزابابایی",
            # Image formset management data
            "images-TOTAL_FORMS": "3",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
            "images-0-image": uploaded_image,
            "images-0-is_primary": "on",
            "images-0-order": "0",
        }

        res = self.client.post(reverse("catalog:item_create"), post_data)
        new_item = Item.objects.filter(title="اره فارسی‌بر ماکیتا").first()
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.owner, self.owner)
        self.assertEqual(new_item.city, "تهران")
        self.assertEqual(new_item.images.count(), 1)
        self.assertTrue(new_item.images.first().is_primary)
        self.assertRedirects(res, reverse("catalog:item_detail", args=[new_item.pk]))

    def test_item_edit_by_owner_succeeds(self):
        """Owner can edit their own item."""
        self.client.force_login(self.owner)
        post_data = {
            "category": self.category.pk,
            "title": "فرز سنگبری رونیکس (ویرایش شده)",
            "description": "توضیحات بروزرسانی شده",
            "brand": "Ronix",
            "condition": Item.Condition.GOOD,
            "daily_price": "90000",
            "deposit_amount": "300000",
            "city": "تهران",
            "neighborhood": "ونک",
            "allow_pickup": "on",
            "allow_courier": "on",
            "address_text": "میدان ونک",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }
        res = self.client.post(reverse("catalog:item_edit", args=[self.item.pk]), post_data)
        self.assertRedirects(res, reverse("catalog:item_detail", args=[self.item.pk]))
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "فرز سنگبری رونیکس (ویرایش شده)")
        self.assertEqual(self.item.daily_price, Decimal("90000"))

    def test_item_edit_by_non_owner_forbidden(self):
        """Non-owner user receives 403 Forbidden when trying to edit an item."""
        self.client.force_login(self.other_user)
        res_get = self.client.get(reverse("catalog:item_edit", args=[self.item.pk]))
        self.assertEqual(res_get.status_code, 403)

        res_post = self.client.post(
            reverse("catalog:item_edit", args=[self.item.pk]),
            {"title": "Hacked Title"},
        )
        self.assertEqual(res_post.status_code, 403)

    def test_item_toggle_active_by_owner(self):
        """Owner can toggle item is_active."""
        self.client.force_login(self.owner)
        self.assertTrue(self.item.is_active)
        res = self.client.post(reverse("catalog:item_toggle_active", args=[self.item.pk]))
        self.assertRedirects(res, reverse("catalog:my_items"))
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

        # Toggle back
        self.client.post(reverse("catalog:item_toggle_active", args=[self.item.pk]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_item_toggle_active_by_non_owner_forbidden(self):
        """Non-owner user receives 403 Forbidden when attempting to toggle status."""
        self.client.force_login(self.other_user)
        res = self.client.post(reverse("catalog:item_toggle_active", args=[self.item.pk]))
        self.assertEqual(res.status_code, 403)

    def test_item_delete_without_rentals_succeeds(self):
        """Owner can delete an item that has no rentals."""
        self.client.force_login(self.owner)
        res = self.client.post(reverse("catalog:item_delete", args=[self.unused_item.pk]))
        self.assertRedirects(res, reverse("catalog:my_items"))
        self.assertFalse(Item.objects.filter(pk=self.unused_item.pk).exists())

    def test_item_delete_by_non_owner_forbidden(self):
        """Non-owner receives 403 Forbidden when attempting to delete an item."""
        self.client.force_login(self.other_user)
        res = self.client.post(reverse("catalog:item_delete", args=[self.unused_item.pk]))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Item.objects.filter(pk=self.unused_item.pk).exists())

    def test_item_delete_with_rentals_blocked(self):
        """Item with existing rentals cannot be deleted; warning shown and item retained."""
        self.client.force_login(self.owner)
        res = self.client.post(reverse("catalog:item_delete", args=[self.item.pk]))
        self.assertRedirects(res, reverse("catalog:my_items"))
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())




class ItemMapLocationTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mapowner",
            email="mapowner@example.com",
            password="StrongPassword123!",
            city="تهران",
            is_email_verified=True,
        )
        self.category = Category.objects.create(name="نقشه‌برداری", slug="surveying")

    def test_item_form_rejects_single_coordinate(self):
        """ItemForm rejects submission when only latitude or only longitude is provided."""
        from catalog.forms import ItemForm

        data = {
            "category": self.category.pk,
            "title": "تراز مهندسی",
            "description": "توضیحات",
            "condition": Item.Condition.NEW,
            "daily_price": "50000",
            "city": "تهران",
            "neighborhood": "انقلاب",
            "allow_pickup": True,
            "latitude": "35.7000",
            # longitude is missing
        }
        form = ItemForm(data)
        self.assertFalse(form.is_valid())
        self.assertTrue(any("مختصات جغرافیایی" in err for err in form.non_field_errors()))

    def test_item_form_rejects_out_of_range_coordinates(self):
        """ItemForm rejects tampered latitude/longitude that exceed valid ranges."""
        from catalog.forms import ItemForm

        data = {
            "category": self.category.pk,
            "title": "دوربین توتال استیشن",
            "description": "توضیحات",
            "condition": Item.Condition.LIKE_NEW,
            "daily_price": "120000",
            "city": "تهران",
            "neighborhood": "امیرآباد",
            "allow_pickup": True,
            "latitude": "95.0000",  # > 90
            "longitude": "195.0000",  # > 180
        }
        form = ItemForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)
        self.assertIn("longitude", form.errors)

    def test_item_create_with_coordinates_persists(self):
        """Owner can pick a point on the map and coordinates are stored in the database."""
        self.client.force_login(self.owner)
        post_data = {
            "category": self.category.pk,
            "title": "جی‌پی‌اس دستی گارمین",
            "description": "جی‌پی‌اس کوهنوردی با دقت بالا",
            "condition": Item.Condition.GOOD,
            "daily_price": "60000",
            "city": "تهران",
            "neighborhood": "تجریش",
            "allow_pickup": "on",
            "address_text": "میدان تجریش، خیابان فناخسرو",
            "latitude": "35.805000",
            "longitude": "51.428000",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }
        res = self.client.post(reverse("catalog:item_create"), post_data)
        item = Item.objects.filter(title="جی‌پی‌اس دستی گارمین").first()
        self.assertIsNotNone(item)
        self.assertRedirects(res, reverse("catalog:item_detail", args=[item.pk]))
        self.assertEqual(item.latitude, Decimal("35.805000"))
        self.assertEqual(item.longitude, Decimal("51.428000"))
        self.assertEqual(item.address_text, "میدان تجریش، خیابان فناخسرو")

    def test_item_detail_shows_map_when_coordinates_present(self):
        """Item detail view renders Leaflet map viewer when coordinates exist."""
        item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="متر لیزری بوش",
            description="متر لیزری ۵۰ متری",
            condition=Item.Condition.NEW,
            daily_price=Decimal("35000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            address_text="میدان ونک، ابتدای ملاصدرا",
            latitude=Decimal("35.757500"),
            longitude=Decimal("51.410000"),
            is_active=True,
        )
        res = self.client.get(reverse("catalog:item_detail", args=[item.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "map-viewer")
        self.assertContains(res, "leaflet.js")
        self.assertContains(res, "میدان ونک، ابتدای ملاصدرا")

    def test_item_detail_shows_only_address_when_coordinates_absent(self):
        """Item without coordinates shows only the address text and no map container."""
        item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="تراز دستی مگنتی",
            description="تراز دستی ۴۰ سانتی",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("20000"),
            city="تهران",
            neighborhood="ستارخان",
            allow_pickup=True,
            address_text="ستارخان، بعد از فلکه اول صادقیه",
            latitude=None,
            longitude=None,
            is_active=True,
        )
        res = self.client.get(reverse("catalog:item_detail", args=[item.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ستارخان، بعد از فلکه اول صادقیه")
        self.assertNotContains(res, "map-viewer")




class ItemRegistrationNotificationTestCase(TestCase):
    def setUp(self):
        from core.models import NotificationLog

        self.owner = User.objects.create_user(
            username="notifowner",
            email="notifowner@example.com",
            password="StrongPassword123!",
            first_name="مهرداد",
            phone="09127778899",
            city="تهران",
            is_email_verified=True,
        )
        self.category = Category.objects.create(name="ابزار تست اعلان", slug="notif-tools")

    def test_item_create_triggers_email_and_sms_notifications(self):
        """Creating a new item sends email and SMS and creates 2 NotificationLog rows linked to the item."""
        from core.models import NotificationLog

        initial_count = NotificationLog.objects.count()
        self.client.force_login(self.owner)

        post_data = {
            "category": self.category.pk,
            "title": "پمپ باد فندکی خودرو",
            "description": "پمپ باد فندکی با نمایشگر دیجیتال فشار باد",
            "condition": Item.Condition.NEW,
            "daily_price": "35000",
            "city": "تهران",
            "neighborhood": "گیشا",
            "allow_pickup": "on",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }
        res = self.client.post(reverse("catalog:item_create"), post_data)
        item = Item.objects.filter(title="پمپ باد فندکی خودرو").first()
        self.assertIsNotNone(item)
        self.assertRedirects(res, reverse("catalog:item_detail", args=[item.pk]))

        # Check 2 notification logs created (email + sms)
        logs = NotificationLog.objects.filter(item=item, event="item_registered")
        self.assertEqual(logs.count(), 2)

        channels = set(logs.values_list("channel", flat=True))
        self.assertEqual(channels, {"email", "sms"})

        for log in logs:
            self.assertEqual(log.user, self.owner)
            self.assertEqual(log.status, "sent")
            self.assertIn("پمپ باد فندکی خودرو", log.body)

    def test_item_edit_does_not_send_notifications(self):
        """Editing an existing item does NOT trigger any notifications."""
        from core.models import NotificationLog

        item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="آچار بکس برقی",
            description="آچار بکس با گشتاور بالا",
            condition=Item.Condition.LIKE_NEW,
            daily_price=Decimal("45000"),
            city="تهران",
            neighborhood="گیشا",
            allow_pickup=True,
            is_active=True,
        )

        logs_before = NotificationLog.objects.filter(item=item).count()
        self.client.force_login(self.owner)

        edit_data = {
            "category": self.category.pk,
            "title": "آچار بکس برقی (ویرایش شده)",
            "description": "توضیحات تکمیلی بدون اعلان",
            "condition": Item.Condition.LIKE_NEW,
            "daily_price": "50000",
            "city": "تهران",
            "neighborhood": "گیشا",
            "allow_pickup": "on",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "10",
        }
        res = self.client.post(reverse("catalog:item_edit", args=[item.pk]), edit_data)
        self.assertRedirects(res, reverse("catalog:item_detail", args=[item.pk]))

        logs_after = NotificationLog.objects.filter(item=item).count()
        self.assertEqual(logs_before, logs_after)
        self.assertEqual(logs_after, 0)




class CatalogSessionFilterTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="itemowner",
            email="itemowner@example.com",
            password="StrongPassword123!",
            phone="09121112233",
            city="تهران",
        )
        self.cat_tools = Category.objects.create(name="ابزارآلات", slug="tools")
        self.cat_camping = Category.objects.create(name="کمپینگ", slug="camping")

        self.drill = Item.objects.create(
            owner=self.owner,
            category=self.cat_tools,
            title="دریل چکشی رونیکس",
            description="دریل قدرتمند",
            daily_price=Decimal("50000"),
            deposit_amount=Decimal("100000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )
        self.tent = Item.objects.create(
            owner=self.owner,
            category=self.cat_camping,
            title="چادر مسافرتی ۴ نفره",
            description="چادر ضدآب",
            daily_price=Decimal("80000"),
            deposit_amount=Decimal("200000"),
            city="اصفهان",
            allow_pickup=True,
            is_active=True,
        )

    def test_search_filters_saved_in_session(self):
        url = reverse("catalog:item_list")
        response = self.client.get(
            url,
            {"q": "دریل", "category": "tools", "city": "تهران", "max_price": "60000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.drill, response.context["items"])
        self.assertNotIn(self.tent, response.context["items"])

        # Check session
        saved = self.client.session.get("catalog_search_filters")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["q"], "دریل")
        self.assertEqual(saved["category"], "tools")
        self.assertEqual(saved["city"], "تهران")
        self.assertEqual(saved["max_price"], "60000")

    def test_search_filters_prefilled_on_subsequent_visit_without_params(self):
        # First visit with query
        url = reverse("catalog:item_list")
        self.client.get(url, {"q": "چادر"})

        # Second visit without any GET params (e.g. returning via navbar)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["q"], "چادر")
        self.assertIn(self.tent, response.context["items"])
        self.assertNotIn(self.drill, response.context["items"])

    def test_clear_removes_filters_from_session(self):
        url = reverse("catalog:item_list")
        # Save filter in session
        self.client.get(url, {"q": "دریل"})
        self.assertIn("catalog_search_filters", self.client.session)

        # Clear filters with ?clear=1
        response = self.client.get(url, {"clear": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("catalog_search_filters", self.client.session)
        self.assertEqual(response.context["q"], "")
        self.assertIn(self.drill, response.context["items"])
        self.assertIn(self.tent, response.context["items"])




class CatalogCookieTests(TestCase):
    """Tests for recent_items signed cookie and last_city cookie in catalog views."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="cookie_owner",
            email="cookie_owner@example.com",
            password="StrongPassword123!",
            city="تهران",
        )
        self.cat = Category.objects.create(name="ابزار", slug="tools")
        self.item1 = Item.objects.create(
            owner=self.owner,
            category=self.cat,
            title="مینی‌فرز رونیکس",
            daily_price=Decimal("50000"),
            city="تهران",
            is_active=True,
        )
        self.item2 = Item.objects.create(
            owner=self.owner,
            category=self.cat,
            title="پمپ باد اینتکس",
            daily_price=Decimal("35000"),
            city="اصفهان",
            is_active=True,
        )

    def test_item_detail_sets_signed_recent_items_and_last_city_cookies(self):
        url = reverse("catalog:item_detail", kwargs={"pk": self.item1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check recent_items signed cookie
        self.assertIn(RECENT_ITEMS_COOKIE, response.cookies)
        recent_cookie = response.cookies[RECENT_ITEMS_COOKIE]
        self.assertTrue(recent_cookie["httponly"])
        self.assertEqual(recent_cookie["max-age"], 7 * 24 * 60 * 60)

        # Verify decoded value contains item1.pk
        req = response.wsgi_request
        # wsgi_request COOKIES contains client sent cookies, client.cookies now has the new cookie
        from django.test import RequestFactory
        check_req = RequestFactory().get("/")
        check_req.COOKIES[RECENT_ITEMS_COOKIE] = recent_cookie.value
        self.assertEqual(get_recent_item_ids(check_req), [self.item1.pk])

        # Check last_city cookie
        self.assertIn(LAST_CITY_COOKIE, response.cookies)
        city_cookie = response.cookies[LAST_CITY_COOKIE]
        self.assertEqual(city_cookie["max-age"], 7 * 24 * 60 * 60)
        check_req.COOKIES[LAST_CITY_COOKIE] = city_cookie.value
        self.assertEqual(get_last_city(check_req), "تهران")

    def test_item_detail_accumulates_and_deduplicates_recent_items(self):
        # Visit item 1
        url1 = reverse("catalog:item_detail", kwargs={"pk": self.item1.pk})
        resp1 = self.client.get(url1)
        self.assertEqual(resp1.status_code, 200)

        # Visit item 2
        url2 = reverse("catalog:item_detail", kwargs={"pk": self.item2.pk})
        resp2 = self.client.get(url2)
        self.assertEqual(resp2.status_code, 200)

        from django.test import RequestFactory
        check_req = RequestFactory().get("/")
        check_req.COOKIES[RECENT_ITEMS_COOKIE] = self.client.cookies[RECENT_ITEMS_COOKIE].value
        self.assertEqual(get_recent_item_ids(check_req), [self.item2.pk, self.item1.pk])
        check_req.COOKIES[LAST_CITY_COOKIE] = self.client.cookies[LAST_CITY_COOKIE].value
        self.assertEqual(get_last_city(check_req), "اصفهان")

        # Visit item 1 again -> should move item1 to front
        resp3 = self.client.get(url1)
        self.assertEqual(resp3.status_code, 200)
        check_req.COOKIES[RECENT_ITEMS_COOKIE] = self.client.cookies[RECENT_ITEMS_COOKIE].value
        self.assertEqual(get_recent_item_ids(check_req), [self.item1.pk, self.item2.pk])
        check_req.COOKIES[LAST_CITY_COOKIE] = self.client.cookies[LAST_CITY_COOKIE].value
        self.assertEqual(get_last_city(check_req), "تهران")

    def test_item_list_sets_last_city_cookie_when_filtered(self):
        url = reverse("catalog:item_list")
        response = self.client.get(url, {"city": "اصفهان"})
        self.assertEqual(response.status_code, 200)

        self.assertIn(LAST_CITY_COOKIE, response.cookies)
        from django.test import RequestFactory
        check_req = RequestFactory().get("/")
        check_req.COOKIES[LAST_CITY_COOKIE] = response.cookies[LAST_CITY_COOKIE].value
        self.assertEqual(get_last_city(check_req), "اصفهان")

    def test_tampered_cookie_ignored_in_item_detail(self):
        self.client.cookies[RECENT_ITEMS_COOKIE] = "tampered:bad_signature"
        url = reverse("catalog:item_detail", kwargs={"pk": self.item2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        from django.test import RequestFactory
        check_req = RequestFactory().get("/")
        check_req.COOKIES[RECENT_ITEMS_COOKIE] = self.client.cookies[RECENT_ITEMS_COOKIE].value
        # Tampered cookie was discarded and new list contains only item2
        self.assertEqual(get_recent_item_ids(check_req), [self.item2.pk])




class CatalogLoggingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="cat_owner",
            password="Password123!",
            phone="09123334455",
            email="owner@example.com",
            is_email_verified=True,
        )
        self.other_user = User.objects.create_user(
            username="cat_other",
            password="Password123!",
            phone="09124445566",
            email="other@example.com",
            is_email_verified=True,
        )
        self.category = Category.objects.create(name="ابزار برقی", slug="tools")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="دریل تخریب",
            daily_price=Decimal("150000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            is_active=True,
        )

    def test_item_create_logs_to_catalog(self):
        self.client.force_login(self.owner)
        url = reverse("catalog:item_create")
        data = {
            "title": "اره فارسی‌بر",
            "category": self.category.pk,
            "daily_price": "200000",
            "deposit_amount": "800000",
            "condition": Item.Condition.GOOD,
            "city": "تهران",
            "neighborhood": "پونک",
            "allow_pickup": "on",
            "allow_courier": "on",
            "description": "دستگاه تمیز و سالم",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "5",
        }
        with self.assertLogs("amanatyab.catalog", level="INFO") as cm:
            resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Item created: item_id=" in msg and "اره فارسی‌بر" in msg for msg in cm.output),
            f"Expected item create log in {cm.output}",
        )

    def test_item_edit_and_toggle_and_delete_logging(self):
        self.client.force_login(self.owner)
        # 1. Edit
        edit_url = reverse("catalog:item_edit", kwargs={"pk": self.item.pk})
        edit_data = {
            "title": "دریل تخریب ارتقایافته",
            "category": self.category.pk,
            "daily_price": "180000",
            "deposit_amount": "500000",
            "condition": Item.Condition.GOOD,
            "city": "تهران",
            "neighborhood": "ونک",
            "allow_pickup": "on",
            "allow_courier": "on",
            "description": "توضیحات جدید",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "5",
        }
        with self.assertLogs("amanatyab.catalog", level="INFO") as cm_edit:
            resp = self.client.post(edit_url, edit_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Item edited: item_id=" in msg for msg in cm_edit.output),
            f"Expected item edit log in {cm_edit.output}",
        )

        # 2. Toggle active
        toggle_url = reverse("catalog:item_toggle_active", kwargs={"pk": self.item.pk})
        with self.assertLogs("amanatyab.catalog", level="INFO") as cm_toggle:
            resp = self.client.post(toggle_url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Item active status toggled: item_id=" in msg and "is_active=False" in msg for msg in cm_toggle.output),
            f"Expected toggle log in {cm_toggle.output}",
        )

        # 3. Delete
        del_url = reverse("catalog:item_delete", kwargs={"pk": self.item.pk})
        with self.assertLogs("amanatyab.catalog", level="INFO") as cm_del:
            resp = self.client.post(del_url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Item deleted: item_id=" in msg for msg in cm_del.output),
            f"Expected delete log in {cm_del.output}",
        )

    def test_permission_denied_warning_logged(self):
        self.client.force_login(self.other_user)
        edit_url = reverse("catalog:item_edit", kwargs={"pk": self.item.pk})
        with self.assertLogs("amanatyab.catalog", level="WARNING") as cm:
            resp = self.client.get(edit_url)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            any("Permission denied on item edit" in msg for msg in cm.output),
            f"Expected permission warning in {cm.output}",
        )





