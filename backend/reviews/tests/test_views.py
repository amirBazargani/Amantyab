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




class ReviewsLoggingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="rev_log_owner",
            password="Password123!",
            phone="09121115599",
            email="revo@example.com",
        )
        self.renter = User.objects.create_user(
            username="rev_log_renter",
            password="Password123!",
            phone="09122226600",
            email="revr@example.com",
        )
        self.third_party = User.objects.create_user(
            username="rev_log_third",
            password="Password123!",
            phone="09123337711",
            email="revt@example.com",
        )
        self.category = Category.objects.create(name="لوازم سفر", slug="travel")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="کوله پشتی کوهنوردی",
            daily_price=Decimal("50000"),
            deposit_amount=Decimal("200000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )
        now = timezone.now()
        self.rental = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now - timedelta(days=3),
            end_at=now - timedelta(days=1),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            status=Rental.Status.COMPLETED,
            rent_amount=Decimal("100000"),
            deposit_amount=Decimal("200000"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("15000"),
            owner_payout=Decimal("85000"),
        )

    def test_review_create_logging(self):
        self.client.force_login(self.renter)
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental.pk})
        data = {
            "rating": 5,
            "comment": "کوله بسیار تمیز و باکیفیت بود",
        }
        with self.assertLogs("amanatyab.reviews", level="INFO") as cm:
            resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Review created: review_id=" in msg and "rating=5" in msg for msg in cm.output),
            f"Expected review create log in {cm.output}",
        )

    def test_permission_denied_warning_logging(self):
        self.client.force_login(self.third_party)
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental.pk})
        with self.assertLogs("amanatyab.reviews", level="WARNING") as cm:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            any("Permission denied on review create" in msg for msg in cm.output),
            f"Expected permission warning log in {cm.output}",
        )

    def test_duplicate_review_warning_logging(self):
        Review.objects.create(
            rental=self.rental,
            reviewer=self.renter,
            reviewee=self.owner,
            reviewee_role=Review.Role.OWNER,
            rating=4,
            comment="خوب بود",
        )
        self.client.force_login(self.renter)
        url = reverse("reviews:review_create", kwargs={"rental_pk": self.rental.pk})
        with self.assertLogs("amanatyab.reviews", level="WARNING") as cm:
            resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            any("Duplicate review attempt" in msg for msg in cm.output),
            f"Expected duplicate review warning log in {cm.output}",
        )

