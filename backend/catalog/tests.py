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
        )
        self.other_user = User.objects.create_user(
            username="otherrenter",
            email="renter@example.com",
            password="StrongPassword123!",
            first_name="سامان",
            phone="09129998877",
            city="تهران",
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

