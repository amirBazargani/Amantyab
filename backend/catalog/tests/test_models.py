from decimal import Decimal
from io import BytesIO

from PIL import Image as PILImage
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase

from catalog.models import Category, Item, ItemImage

User = get_user_model()


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
        with self.assertRaises(IntegrityError):
            Item.objects.create(
                owner=self.owner,
                category=self.category,
                title="Invalid Lat Only",
                description="desc",
                condition=Item.Condition.NEW,
                daily_price=Decimal("50000"),
                city="تهران",
                neighborhood="ونک",
                allow_pickup=True,
                latitude=Decimal("35.6892"),
                longitude=None,
            )

    def test_lng_without_lat_raises_integrity_error(self):
        """Item with longitude set but latitude None violates DB constraint."""
        with self.assertRaises(IntegrityError):
            Item.objects.create(
                owner=self.owner,
                category=self.category,
                title="Invalid Lng Only",
                description="desc",
                condition=Item.Condition.NEW,
                daily_price=Decimal("50000"),
                city="تهران",
                neighborhood="ونک",
                allow_pickup=True,
                latitude=None,
                longitude=Decimal("51.3890"),
            )

    def test_latitude_120_fails_full_clean(self):
        """Item with latitude > 90 fails full_clean() validation."""
        item = Item(
            owner=self.owner,
            category=self.category,
            title="Invalid Lat Value",
            description="desc",
            condition=Item.Condition.NEW,
            daily_price=Decimal("50000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            latitude=Decimal("120.0"),
            longitude=Decimal("51.3890"),
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_latitude_negative_out_of_bounds_fails(self):
        """Item with latitude < -90 fails full_clean() validation."""
        item = Item(
            owner=self.owner,
            category=self.category,
            title="Invalid Lat Negative",
            description="desc",
            condition=Item.Condition.NEW,
            daily_price=Decimal("50000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            latitude=Decimal("-95.0"),
            longitude=Decimal("51.3890"),
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_longitude_out_of_bounds_fails(self):
        """Item with longitude > 180 or < -180 fails full_clean() validation."""
        item_high = Item(
            owner=self.owner,
            category=self.category,
            title="Invalid Lng High",
            description="desc",
            condition=Item.Condition.NEW,
            daily_price=Decimal("50000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            latitude=Decimal("35.0"),
            longitude=Decimal("185.0"),
        )
        with self.assertRaises(ValidationError) as ctx:
            item_high.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)

        item_low = Item(
            owner=self.owner,
            category=self.category,
            title="Invalid Lng Low",
            description="desc",
            condition=Item.Condition.NEW,
            daily_price=Decimal("50000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            latitude=Decimal("35.0"),
            longitude=Decimal("-185.0"),
        )
        with self.assertRaises(ValidationError) as ctx:
            item_low.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)

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

    def test_both_coords_none_is_valid(self):
        """Item with both coords None passes validation."""
        item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="No Coords Item",
            description="desc",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("50000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            latitude=None,
            longitude=None,
        )
        item.full_clean()
        self.assertIsNone(item.latitude)
        self.assertIsNone(item.longitude)


class ItemModelConstraintTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="itemuser",
            email="itemuser@example.com",
            password="StrongPassword123!",
        )
        self.category = Category.objects.create(name="ابزار ساختمانی", slug="construction")

    def test_item_creation_and_str(self):
        item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="فرز سنگبری رونیکس",
            description="قدرت بالا",
            condition=Item.Condition.NEW,
            daily_price=Decimal("120000"),
            deposit_amount=Decimal("300000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
        )
        self.assertEqual(str(item), "فرز سنگبری رونیکس")
        self.assertEqual(item.condition, Item.Condition.NEW)

    def test_category_hierarchy_and_str(self):
        subcat = Category.objects.create(
            name="سنگ‌فرز",
            slug="grinders",
            parent=self.category,
        )
        self.assertEqual(str(self.category), "ابزار ساختمانی")
        self.assertEqual(subcat.parent, self.category)


class ItemImageResizingTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="imguser",
            email="img@example.com",
            password="StrongPassword123!",
        )
        self.category = Category.objects.create(name="ابزار تست", slug="tools-img")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="کالای تست تصویر",
            description="توضیحات",
            daily_price=Decimal("50000"),
            city="تهران",
        )

    def _create_uploaded_image(self, width, height, name="test.jpg"):
        im = PILImage.new("RGB", (width, height), color="blue")
        buf = BytesIO()
        im.save(buf, format="JPEG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")

    def test_large_image_resized_to_max_1200px(self):
        """Image larger than 1200px on longest side is resized proportionally on save."""
        uploaded = self._create_uploaded_image(2000, 1000, "large.jpg")
        img_obj = ItemImage.objects.create(item=self.item, image=uploaded, is_primary=True)

        with PILImage.open(img_obj.image.path) as img:
            w, h = img.size
            self.assertEqual(w, 1200)
            self.assertEqual(h, 600)

        img_obj.image.delete(save=False)

    def test_small_image_not_enlarged(self):
        """Image with dimensions <= 1200px is not resized/enlarged."""
        uploaded = self._create_uploaded_image(800, 600, "small.jpg")
        img_obj = ItemImage.objects.create(item=self.item, image=uploaded)

        with PILImage.open(img_obj.image.path) as img:
            w, h = img.size
            self.assertEqual(w, 800)
            self.assertEqual(h, 600)

        img_obj.image.delete(save=False)

    def test_primary_image_property_prefetched_and_unprefetched(self):
        """Item.primary_image returns primary image correctly both with and without prefetch."""
        img1 = ItemImage.objects.create(
            item=self.item,
            image=self._create_uploaded_image(200, 200, "1.jpg"),
            is_primary=False,
            order=1,
        )
        img2 = ItemImage.objects.create(
            item=self.item,
            image=self._create_uploaded_image(200, 200, "2.jpg"),
            is_primary=True,
            order=2,
        )

        # Unprefetched
        item_fresh = Item.objects.get(pk=self.item.pk)
        self.assertEqual(item_fresh.primary_image.pk, img2.pk)

        # Prefetched
        item_prefetched = Item.objects.prefetch_related("images").get(pk=self.item.pk)
        with self.assertNumQueries(0):
            self.assertEqual(item_prefetched.primary_image.pk, img2.pk)

        img1.image.delete(save=False)
        img2.image.delete(save=False)
