from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Item
from rentals.models import Rental
from reviews.forms import ReviewForm
from reviews.models import Review

User = get_user_model()

class ReviewQuerySetTests(TestCase):
    def setUp(self):
        self.user_owner = User.objects.create_user(
            username="rev_owner", email="rev_owner@example.com", password="PassWord123!"
        )
        self.user_renter = User.objects.create_user(
            username="rev_renter", email="rev_renter@example.com", password="PassWord123!"
        )
        self.other_user = User.objects.create_user(
            username="rev_other", email="rev_other@example.com", password="PassWord123!"
        )
        self.category = Category.objects.create(name="صوتی", slug="audio")
        self.item = Item.objects.create(
            owner=self.user_owner,
            category=self.category,
            title="میکروفون استودیویی رود",
            condition=Item.Condition.NEW,
            daily_price=Decimal("100000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            is_active=True,
        )

        now = timezone.now()
        self.rental1 = Rental.objects.create(
            item=self.item,
            renter=self.user_renter,
            start_at=now - timedelta(days=5),
            end_at=now - timedelta(days=3),
            status=Rental.Status.COMPLETED,
            rent_amount=Decimal("200000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("30000"),
            owner_payout=Decimal("170000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        self.rental2 = Rental.objects.create(
            item=self.item,
            renter=self.other_user,
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(days=1),
            status=Rental.Status.COMPLETED,
            rent_amount=Decimal("100000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("15000"),
            owner_payout=Decimal("85000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )

        # Reviews for owner: rating 5 and rating 3 -> average 4.0
        self.rev1 = Review.objects.create(
            rental=self.rental1,
            reviewer=self.user_renter,
            reviewee=self.user_owner,
            reviewee_role=Review.Role.OWNER,
            rating=5,
            comment="عالی",
        )
        self.rev2 = Review.objects.create(
            rental=self.rental2,
            reviewer=self.other_user,
            reviewee=self.user_owner,
            reviewee_role=Review.Role.OWNER,
            rating=3,
            comment="متوسط",
        )
        # Review for renter: rating 4
        self.rev3 = Review.objects.create(
            rental=self.rental1,
            reviewer=self.user_owner,
            reviewee=self.user_renter,
            reviewee_role=Review.Role.RENTER,
            rating=4,
            comment="مستأجر خوب",
        )

    def test_for_user(self):
        owner_reviews = Review.objects.for_user(self.user_owner)
        self.assertEqual(owner_reviews.count(), 2)
        self.assertIn(self.rev1, owner_reviews)
        self.assertIn(self.rev2, owner_reviews)

        # With role filter
        owner_role_reviews = Review.objects.for_user(
            self.user_owner, role=Review.Role.OWNER
        )
        self.assertEqual(owner_role_reviews.count(), 2)

        renter_reviews = Review.objects.for_user(
            self.user_renter, role=Review.Role.RENTER
        )
        self.assertEqual(renter_reviews.count(), 1)
        self.assertIn(self.rev3, renter_reviews)

    def test_average_rating(self):
        owner_avg = Review.objects.for_user(self.user_owner).average_rating()
        self.assertEqual(owner_avg, 4.0)

        renter_avg = Review.objects.for_user(self.user_renter).average_rating()
        self.assertEqual(renter_avg, 4.0)

        # User with no reviews
        other_avg = Review.objects.for_user(self.other_user).average_rating()
        self.assertIsNone(other_avg)


