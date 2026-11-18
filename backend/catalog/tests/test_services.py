from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Category, Item
from rentals.models import Rental

User = get_user_model()


class ItemQuerySetTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="qs_user1", email="qs1@example.com", password="PassWord123!"
        )
        self.user2 = User.objects.create_user(
            username="qs_user2", email="qs2@example.com", password="PassWord123!"
        )
        self.cat_parent = Category.objects.create(name="ابزار برقی", slug="power-tools")
        self.cat_child = Category.objects.create(
            name="دریل و پیچ‌گوشتی", slug="drills", parent=self.cat_parent
        )
        self.cat_other = Category.objects.create(name="وسایل کمپینگ", slug="camping")

        self.item1 = Item.objects.create(
            owner=self.user1,
            category=self.cat_child,
            title="دریل چکشی بوش",
            description="دریل قدرتمند خانگی بوش",
            brand="Bosch",
            condition=Item.Condition.LIKE_NEW,
            daily_price=Decimal("150000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            is_active=True,
        )
        self.item2 = Item.objects.create(
            owner=self.user2,
            category=self.cat_other,
            title="چادر کوهنوردی ۴ نفره",
            description="چادر کلمن ضدآب",
            brand="Coleman",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("250000"),
            city="اصفهان",
            neighborhood="مرداویج",
            allow_pickup=True,
            is_active=True,
        )
        self.item_inactive = Item.objects.create(
            owner=self.user1,
            category=self.cat_child,
            title="اره فارسی بر ماکیتا",
            description="اره غیرفعال",
            brand="Makita",
            condition=Item.Condition.NEW,
            daily_price=Decimal("300000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            is_active=False,
        )

    def test_active(self):
        qs = Item.objects.active()
        self.assertIn(self.item1, qs)
        self.assertIn(self.item2, qs)
        self.assertNotIn(self.item_inactive, qs)

    def test_in_city(self):
        tehran_qs = Item.objects.in_city("تهران")
        self.assertIn(self.item1, tehran_qs)
        self.assertNotIn(self.item2, tehran_qs)

        self.assertEqual(Item.objects.in_city("").count(), Item.objects.count())

    def test_in_category(self):
        child_qs = Item.objects.in_category(self.cat_child)
        self.assertIn(self.item1, child_qs)
        self.assertNotIn(self.item2, child_qs)

        by_slug = Item.objects.in_category("drills")
        self.assertIn(self.item1, by_slug)

        by_id = Item.objects.in_category(str(self.cat_child.pk))
        self.assertIn(self.item1, by_id)

        parent_qs = Item.objects.in_category(self.cat_parent)
        self.assertIn(self.item1, parent_qs)
        self.assertNotIn(self.item2, parent_qs)

    def test_search(self):
        self.assertIn(self.item1, Item.objects.search("چکشی"))
        self.assertIn(self.item2, Item.objects.search("ضدآب"))
        self.assertIn(self.item1, Item.objects.search("bosch"))
        self.assertEqual(Item.objects.search("").count(), Item.objects.count())

    def test_price_up_to(self):
        qs = Item.objects.price_up_to("200000")
        self.assertIn(self.item1, qs)
        self.assertNotIn(self.item2, qs)

        self.assertEqual(Item.objects.price_up_to("invalid").count(), Item.objects.count())

    def test_available_between(self):
        now = timezone.now()
        start = now + timedelta(days=2)
        end = now + timedelta(days=4)

        Rental.objects.create(
            item=self.item1,
            renter=self.user2,
            start_at=start,
            end_at=end,
            status=Rental.Status.CONFIRMED,
            rent_amount=Decimal("300000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("45000"),
            owner_payout=Decimal("255000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )

        available = Item.objects.available_between(
            start + timedelta(hours=1), end - timedelta(hours=1)
        )
        self.assertNotIn(self.item1, available)
        self.assertIn(self.item2, available)

    def test_chained_methods(self):
        qs = (
            Item.objects.active()
            .in_city("تهران")
            .in_category("power-tools")
            .search("بوش")
            .price_up_to("200000")
        )
        self.assertEqual(list(qs), [self.item1])
