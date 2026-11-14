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

    def test_form_validation(self):
        form_valid = ReviewForm(data={"rating": 5, "comment": "عالی"})
        self.assertTrue(form_valid.is_valid())
        self.assertEqual(form_valid.cleaned_data["rating"], 5)

        form_invalid_rating = ReviewForm(data={"rating": 6, "comment": "بد"})
        self.assertFalse(form_invalid_rating.is_valid())


class ReviewViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="vw_owner",
            email="vw_owner@test.ir",
            password="Password123!",
            phone="09121111114",
        )
        self.renter = User.objects.create_user(
            username="vw_renter",
            email="vw_renter@test.ir",
            password="Password123!",
            phone="09122222225",
        )
        self.stranger = User.objects.create_user(
            username="vw_stranger",
            email="vw_stranger@test.ir",
            password="Password123!",
            phone="09123333336",
        )
        self.category = Category.objects.create(name="تجهیزات", slug="equipment")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="دریل بتن‌کن",
            description="دریل حرفه‌ای",
            condition=Item.Condition.NEW,
            daily_price=Decimal("200000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )

        now = timezone.now()
        self.rental_completed = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now - timedelta(days=4),
            end_at=now - timedelta(days=1),
            status=Rental.Status.COMPLETED,
            rent_amount=Decimal("600000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("90000"),
            owner_payout=Decimal("510000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )

        self.rental_active = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now,
            end_at=now + timedelta(days=2),
            status=Rental.Status.CONFIRMED,
            rent_amount=Decimal("400000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("60000"),
            owner_payout=Decimal("340000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )

    def test_anonymous_redirected(self):
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental_completed.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_stranger_forbidden(self):
        self.client.login(username="vw_stranger", password="Password123!")
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental_completed.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_non_completed_rental_redirects_with_message(self):
        self.client.login(username="vw_renter", password="Password123!")
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental_active.pk})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تنها پس از پایان و تکمیل")

    def test_renter_submits_review_successfully(self):
        self.client.login(username="vw_renter", password="Password123!")
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental_completed.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ثبت نظر و امتیاز")

        post_data = {"rating": 5, "comment": "تجربه بسیار خوبی بود، دستگاه کاملاً سالم بود."}
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نظر و امتیاز شما با موفقیت ثبت شد")

        review = Review.objects.get(rental=self.rental_completed, reviewer=self.renter)
        self.assertEqual(review.reviewee, self.owner)
        self.assertEqual(review.reviewee_role, Review.Role.OWNER)
        self.assertEqual(review.rating, 5)

        # Attempting second review by same renter redirects with warning
        response_dup = self.client.get(url, follow=True)
        self.assertContains(response_dup, "قبلاً نظر و امتیاز خود را")

    def test_owner_submits_review_successfully(self):
        self.client.login(username="vw_owner", password="Password123!")
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental_completed.pk})

        post_data = {"rating": 4, "comment": "امانت‌گیرنده خوش‌قول و تمیز"}
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        review = Review.objects.get(rental=self.rental_completed, reviewer=self.owner)
        self.assertEqual(review.reviewee, self.renter)
        self.assertEqual(review.reviewee_role, Review.Role.RENTER)
        self.assertEqual(review.rating, 4)

    def test_averages_on_item_and_profile_pages(self):
        # Create reviews:
        # Renter reviews owner 4 stars for item
        Review.objects.create(
            rental=self.rental_completed,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=4,
            comment="دستگاه عالی بود",
        )
        # Owner reviews renter 5 stars
        Review.objects.create(
            rental=self.rental_completed,
            reviewer=self.owner,
            reviewee=self.renter,
            reviewee_role=Review.Role.RENTER,
            rating=5,
            comment="امانت‌گیرنده بسیار عالی",
        )

        # Check item page
        item_url = reverse("catalog:item_detail", kwargs={"pk": self.item.pk})
        response = self.client.get(item_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "4.0")
        self.assertContains(response, "دستگاه عالی بود")

        # Check owner's profile page
        owner_profile_url = reverse("accounts:public_profile", kwargs={"username": self.owner.username})
        response = self.client.get(owner_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "4.0")
        self.assertContains(response, "دستگاه عالی بود")

        # Check renter's profile page
        renter_profile_url = reverse("accounts:public_profile", kwargs={"username": self.renter.username})
        response = self.client.get(renter_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "5.0")
        self.assertContains(response, "امانت‌گیرنده بسیار عالی")


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
