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

class ReviewModelAndFormTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="item_owner",
            email="owner@test.ir",
            password="Password123!",
            phone="09121111111",
        )
        self.renter = User.objects.create_user(
            username="item_renter",
            email="renter@test.ir",
            password="Password123!",
            phone="09122222222",
        )
        self.stranger = User.objects.create_user(
            username="stranger",
            email="stranger@test.ir",
            password="Password123!",
            phone="09123333333",
        )
        self.category = Category.objects.create(name="ابزارآلات", slug="tools")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="فرز سنگبری",
            description="فرز با کیفیت بالا",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("150000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            is_active=True,
        )

        now = timezone.now()
        self.rental_completed = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now - timedelta(days=5),
            end_at=now - timedelta(days=2),
            status=Rental.Status.COMPLETED,
            rent_amount=Decimal("450000"),
            deposit_amount=Decimal("500000"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("67500"),
            owner_payout=Decimal("382500"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )

        self.rental_ongoing = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now,
            end_at=now + timedelta(days=2),
            status=Rental.Status.HANDED_OVER,
            rent_amount=Decimal("300000"),
            deposit_amount=Decimal("500000"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("45000"),
            owner_payout=Decimal("255000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )

    def test_review_creation_valid_renter_reviews_owner(self):
        review = Review(
            rental=self.rental_completed,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=5,
            comment="بسیار عالی و دقیق",
        )
        review.full_clean()
        review.save()
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(review.rating, 5)

    def test_review_creation_valid_owner_reviews_renter(self):
        review = Review(
            rental=self.rental_completed,
            reviewer=self.owner,
            reviewee=self.renter,
            reviewee_role=Review.Role.RENTER,
            rating=4,
            comment="کالا کاملاً سالم برگشت داده شد",
        )
        review.full_clean()
        review.save()
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(review.rating, 4)

    def test_review_rejected_for_non_completed_rental(self):
        review = Review(
            rental=self.rental_ongoing,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=5,
        )
        with self.assertRaises(ValidationError) as ctx:
            review.full_clean()
        self.assertIn("rental", ctx.exception.message_dict)

    def test_review_rejected_for_self_review(self):
        review = Review(
            rental=self.rental_completed,
            reviewer=self.renter,
            reviewee=self.renter,
            reviewee_role=Review.Role.OWNER,
            rating=5,
        )
        with self.assertRaises(ValidationError) as ctx:
            review.full_clean()
        self.assertIn("reviewee", ctx.exception.message_dict)

    def test_review_rejected_for_stranger(self):
        review = Review(
            rental=self.rental_completed,
            reviewer=self.stranger,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=5,
        )
        with self.assertRaises(ValidationError) as ctx:
            review.full_clean()
        self.assertIn("reviewer", ctx.exception.message_dict)

    def test_review_rejected_for_mismatched_roles(self):
        # Renter reviewing owner but specifies role 'renter'
        review = Review(
            rental=self.rental_completed,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.RENTER,
            rating=5,
        )
        with self.assertRaises(ValidationError) as ctx:
            review.full_clean()
        self.assertIn("reviewee_role", ctx.exception.message_dict)

    def test_unique_rental_reviewer_constraint(self):
        Review.objects.create(
            rental=self.rental_completed,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=5,
        )
        duplicate = Review(
            rental=self.rental_completed,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=4,
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            duplicate.save()

