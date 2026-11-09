from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Item
from .forms import RentalRequestForm
from .models import Payment, Rental
from .services import (
    calculate_price,
    create_rental,
    has_overlap,
    simulate_payment,
)

User = get_user_model()


class RentalGeoFieldsTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="rentalowner",
            email="owner@rentals.test",
            password="StrongPassword123!",
            phone="09121111112",
        )
        self.renter = User.objects.create_user(
            username="rentalrenter",
            email="renter@rentals.test",
            password="StrongPassword123!",
            phone="09122222223",
        )
        self.category = Category.objects.create(name="ابزار", slug="tools-rental")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="دریل هیلتی",
            description="دریل قوی",
            condition=Item.Condition.NEW,
            daily_price=Decimal("100000"),
            city="تهران",
            allow_pickup=True,
            allow_courier=True,
        )

    def test_delivery_lat_without_lng_raises_integrity_error(self):
        """Rental with delivery_latitude set but delivery_longitude None violates DB constraint."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)

        with self.assertRaises(IntegrityError):
            Rental.objects.create(
                item=self.item,
                renter=self.renter,
                start_at=start,
                end_at=end,
                rent_amount=Decimal("200000"),
                delivery_method=Rental.DeliveryMethod.COURIER,
                delivery_address="خیابان آزادی",
                delivery_latitude=Decimal("35.700000"),
                delivery_longitude=None,
            )

    def test_delivery_latitude_120_fails_full_clean(self):
        """Rental with delivery_latitude > 90 fails full_clean() validation."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)

        rental = Rental(
            item=self.item,
            renter=self.renter,
            start_at=start,
            end_at=end,
            rent_amount=Decimal("200000"),
            delivery_method=Rental.DeliveryMethod.COURIER,
            delivery_address="خیابان آزادی",
            delivery_latitude=Decimal("120.000000"),
            delivery_longitude=Decimal("51.350000"),
        )
        with self.assertRaises(ValidationError) as ctx:
            rental.full_clean()
        self.assertIn("delivery_latitude", ctx.exception.message_dict)

    def test_valid_delivery_coordinates_and_reminder_sent_at(self):
        """Rental with valid delivery coordinates and reminder timestamp saves cleanly."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        reminder_time = timezone.now()

        rental = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=start,
            end_at=end,
            rent_amount=Decimal("200000"),
            delivery_method=Rental.DeliveryMethod.COURIER,
            delivery_address="تهران، خیابان ولیعصر، نرسیده به میدان ونک",
            delivery_latitude=Decimal("35.750000"),
            delivery_longitude=Decimal("51.410000"),
            reminder_sent_at=reminder_time,
        )
        rental.full_clean()
        self.assertEqual(rental.delivery_address, "تهران، خیابان ولیعصر، نرسیده به میدان ونک")
        self.assertEqual(rental.delivery_latitude, Decimal("35.750000"))
        self.assertEqual(rental.delivery_longitude, Decimal("51.410000"))
        self.assertEqual(rental.reminder_sent_at, reminder_time)


class PricingServiceTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="itemowner",
            email="owner@price.test",
            password="StrongPassword123!",
            phone="09121111113",
        )
        self.category = Category.objects.create(name="ابزار", slug="tools-pricing")
        self.item_with_hourly = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="کارواش خانگی",
            description="مناسب شستشو",
            condition=Item.Condition.LIKE_NEW,
            hourly_price=Decimal("20000"),
            daily_price=Decimal("120000"),
            deposit_amount=Decimal("300000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=True,
        )
        self.item_daily_only = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="چادر مسافرتی",
            description="۸ نفره",
            condition=Item.Condition.GOOD,
            hourly_price=None,
            daily_price=Decimal("80000"),
            deposit_amount=Decimal("0"),
            city="تهران",
            neighborhood="سعادت‌آباد",
            allow_pickup=True,
        )

    def test_hourly_pricing_under_24_hours(self):
        """Under 24h with hourly_price sets pricing_type=hourly and ceil(hours)*hourly_price."""
        start = timezone.now()
        # Exactly 3 hours
        end = start + timedelta(hours=3)
        res = calculate_price(self.item_with_hourly, start, end)
        self.assertEqual(res["pricing_type"], "hourly")
        self.assertEqual(res["units_billed"], 3)
        self.assertEqual(res["rent_amount"], Decimal("60000"))
        self.assertEqual(res["deposit_amount"], Decimal("300000"))
        self.assertEqual(res["commission_amount"], Decimal("9000"))  # 15% of 60,000
        self.assertEqual(res["owner_payout"], Decimal("51000"))
        self.assertEqual(res["total_amount"], Decimal("360000"))

    def test_hourly_pricing_ceil_fraction(self):
        """Duration of 1 hour and 10 minutes rounds up to 2 hours."""
        start = timezone.now()
        end = start + timedelta(hours=1, minutes=10)
        res = calculate_price(self.item_with_hourly, start, end)
        self.assertEqual(res["pricing_type"], "hourly")
        self.assertEqual(res["units_billed"], 2)
        self.assertEqual(res["rent_amount"], Decimal("40000"))

    def test_daily_pricing_at_24_hours(self):
        """Duration of exactly 24 hours falls to daily pricing."""
        start = timezone.now()
        end = start + timedelta(hours=24)
        res = calculate_price(self.item_with_hourly, start, end)
        self.assertEqual(res["pricing_type"], "daily")
        self.assertEqual(res["units_billed"], 1)
        self.assertEqual(res["rent_amount"], Decimal("120000"))
        self.assertEqual(res["commission_amount"], Decimal("18000"))  # 15% of 120,000
        self.assertEqual(res["owner_payout"], Decimal("102000"))

    def test_daily_pricing_over_24_hours_rounds_up(self):
        """Duration of 25 hours rounds up to 2 days."""
        start = timezone.now()
        end = start + timedelta(hours=25)
        res = calculate_price(self.item_with_hourly, start, end)
        self.assertEqual(res["pricing_type"], "daily")
        self.assertEqual(res["units_billed"], 2)
        self.assertEqual(res["rent_amount"], Decimal("240000"))

    def test_item_without_hourly_price_uses_daily_pricing(self):
        """Item without hourly_price always calculates based on daily rate even for short duration."""
        start = timezone.now()
        end = start + timedelta(hours=5)
        res = calculate_price(self.item_daily_only, start, end)
        self.assertEqual(res["pricing_type"], "daily")
        self.assertEqual(res["units_billed"], 1)
        self.assertEqual(res["rent_amount"], Decimal("80000"))
        self.assertEqual(res["deposit_amount"], Decimal("0"))

    def test_invalid_dates_raises_value_error(self):
        """End time before or equal to start time raises ValueError."""
        start = timezone.now()
        end = start - timedelta(hours=1)
        with self.assertRaises(ValueError):
            calculate_price(self.item_with_hourly, start, end)

        with self.assertRaises(ValueError):
            calculate_price(self.item_with_hourly, start, start)


class OverlapAndRentalServiceTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner2",
            email="owner2@service.test",
            password="StrongPassword123!",
            phone="09121111114",
        )
        self.renter1 = User.objects.create_user(
            username="renter1",
            email="renter1@service.test",
            password="StrongPassword123!",
            phone="09122222224",
        )
        self.renter2 = User.objects.create_user(
            username="renter2",
            email="renter2@service.test",
            password="StrongPassword123!",
            phone="09122222225",
        )
        self.category = Category.objects.create(name="دیجیتال", slug="digital-service")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="دوربین عکاسی کانن",
            description="دوربین حرفه‌ای",
            condition=Item.Condition.LIKE_NEW,
            hourly_price=Decimal("50000"),
            daily_price=Decimal("250000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            allow_pickup=True,
            allow_courier=True,
        )

    def test_has_overlap_detection(self):
        """Overlapping intervals are detected; adjacent intervals are not."""
        base = timezone.now() + timedelta(days=2)
        start1 = base
        end1 = base + timedelta(days=2)

        # Existing confirmed rental
        r1 = Rental.objects.create(
            item=self.item,
            renter=self.renter1,
            start_at=start1,
            end_at=end1,
            status=Rental.Status.CONFIRMED,
            rent_amount=Decimal("500000"),
            deposit_amount=Decimal("500000"),
        )

        # Overlapping period (middle)
        self.assertTrue(has_overlap(self.item, start1 + timedelta(hours=5), end1 - timedelta(hours=5)))
        # Overlapping period (starts before, ends inside)
        self.assertTrue(has_overlap(self.item, start1 - timedelta(hours=5), start1 + timedelta(hours=5)))
        # Overlapping period (starts inside, ends after)
        self.assertTrue(has_overlap(self.item, end1 - timedelta(hours=5), end1 + timedelta(hours=5)))
        # Adjacent before: end equals start1 -> NOT overlapping
        self.assertFalse(has_overlap(self.item, start1 - timedelta(days=1), start1))
        # Adjacent after: start equals end1 -> NOT overlapping
        self.assertFalse(has_overlap(self.item, end1, end1 + timedelta(days=1)))

        # Exclude self works
        self.assertFalse(has_overlap(self.item, start1, end1, exclude_rental_id=r1.pk))

    def test_cancelled_rentals_do_not_cause_overlap(self):
        """Cancelled rentals do not block future bookings."""
        base = timezone.now() + timedelta(days=5)
        Rental.objects.create(
            item=self.item,
            renter=self.renter1,
            start_at=base,
            end_at=base + timedelta(days=1),
            status=Rental.Status.CANCELLED,
            rent_amount=Decimal("250000"),
        )
        self.assertFalse(has_overlap(self.item, base, base + timedelta(days=1)))

    def test_create_rental_success(self):
        """create_rental creates a Rental in pending_payment status with calculated price."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        rental = create_rental(
            renter=self.renter1,
            item=self.item,
            start_at=start,
            end_at=end,
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        self.assertEqual(rental.status, Rental.Status.PENDING_PAYMENT)
        self.assertEqual(rental.rent_amount, Decimal("200000"))  # 4 * 50,000
        self.assertEqual(rental.deposit_amount, Decimal("500000"))
        self.assertEqual(rental.commission_amount, Decimal("30000"))  # 15% of 200,000
        self.assertEqual(rental.owner_payout, Decimal("170000"))

    def test_create_rental_by_owner_raises_validation_error(self):
        """Owner cannot rent their own item."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        with self.assertRaises(ValidationError):
            create_rental(
                renter=self.owner,
                item=self.item,
                start_at=start,
                end_at=end,
            )

    def test_create_rental_with_overlap_raises_validation_error(self):
        """Creating an overlapping rental raises ValidationError."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        create_rental(
            renter=self.renter1,
            item=self.item,
            start_at=start,
            end_at=end,
        )
        with self.assertRaises(ValidationError):
            create_rental(
                renter=self.renter2,
                item=self.item,
                start_at=start + timedelta(hours=6),
                end_at=end + timedelta(hours=6),
            )


class SimulatePaymentServiceTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="payowner",
            email="payowner@test.com",
            password="StrongPassword123!",
            phone="09121111115",
        )
        self.renter = User.objects.create_user(
            username="payrenter",
            email="payrenter@test.com",
            password="StrongPassword123!",
            phone="09122222226",
        )
        self.category = Category.objects.create(name="ورزشی", slug="sports")
        self.item_with_deposit = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="دوچرخه کوهستان",
            description="دنده‌ای",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("150000"),
            deposit_amount=Decimal("400000"),
            city="تهران",
            allow_pickup=True,
        )
        self.item_zero_deposit = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="راکت تنیس",
            description="حرفه‌ای",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("70000"),
            deposit_amount=Decimal("0"),
            city="تهران",
            allow_pickup=True,
        )

    def test_simulate_payment_creates_rent_and_deposit_rows(self):
        """Simulated payment creates both rent and deposit payments, sets confirmed status and tracking code."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item_with_deposit,
            start_at=start,
            end_at=end,
        )
        self.assertIsNone(rental.tracking_code)
        self.assertEqual(rental.status, Rental.Status.PENDING_PAYMENT)

        rental, payments = simulate_payment(rental)
        rental.refresh_from_db()

        self.assertEqual(rental.status, Rental.Status.CONFIRMED)
        self.assertTrue(rental.tracking_code.startswith("AMN-"))
        self.assertEqual(len(payments), 2)

        rent_pmt = payments[0]
        self.assertEqual(rent_pmt.kind, Payment.Kind.RENT)
        self.assertEqual(rent_pmt.amount, rental.rent_amount)
        self.assertEqual(rent_pmt.status, Payment.Status.SUCCESS)
        self.assertTrue(rent_pmt.receipt_no.startswith("RCP-RENT-"))

        dep_pmt = payments[1]
        self.assertEqual(dep_pmt.kind, Payment.Kind.DEPOSIT)
        self.assertEqual(dep_pmt.amount, rental.deposit_amount)
        self.assertEqual(dep_pmt.status, Payment.Status.SUCCESS)
        self.assertTrue(dep_pmt.receipt_no.startswith("RCP-DEP-"))

    def test_simulate_payment_zero_deposit(self):
        """Simulated payment creates only one payment row (rent) when deposit is 0."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item_zero_deposit,
            start_at=start,
            end_at=end,
        )
        rental, payments = simulate_payment(rental)
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].kind, Payment.Kind.RENT)

    def test_simulate_payment_rejects_already_confirmed(self):
        """simulate_payment raises ValidationError if rental is already confirmed."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item_zero_deposit,
            start_at=start,
            end_at=end,
        )
        simulate_payment(rental)

        with self.assertRaises(ValidationError):
            simulate_payment(rental)


class RentalRequestFormTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="formowner",
            email="formowner@test.com",
            password="StrongPassword123!",
            phone="09121111116",
        )
        self.renter = User.objects.create_user(
            username="formrenter",
            email="formrenter@test.com",
            password="StrongPassword123!",
            phone="09122222227",
        )
        self.category = Category.objects.create(name="تجهیزات", slug="equipments")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="پروژکتور فیلم",
            description="کیفیت 4K",
            condition=Item.Condition.NEW,
            daily_price=Decimal("200000"),
            city="تهران",
            allow_pickup=True,
            allow_courier=True,
        )

    def test_form_valid_data(self):
        """Valid rental form submissions validate cleanly."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=3)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.PICKUP,
            "delivery_address": "",
        }
        form = RentalRequestForm(data=data, item=self.item, user=self.renter)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_owner_cannot_rent_own_item(self):
        """Owner attempting to submit form for own item fails validation."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=3)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.PICKUP,
        }
        form = RentalRequestForm(data=data, item=self.item, user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn("امکان ثبت درخواست اجاره برای کالای متعلق به خودتان وجود ندارد.", form.non_field_errors())

    def test_form_courier_requires_address(self):
        """Courier delivery method requires delivery_address."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=3)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.COURIER,
            "delivery_address": "   ",
        }
        form = RentalRequestForm(data=data, item=self.item, user=self.renter)
        self.assertFalse(form.is_valid())
        self.assertIn("delivery_address", form.errors)

    def test_form_past_start_date_fails(self):
        """Start date in past fails validation."""
        start = timezone.now() - timedelta(hours=2)
        end = timezone.now() + timedelta(days=1)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.PICKUP,
        }
        form = RentalRequestForm(data=data, item=self.item, user=self.renter)
        self.assertFalse(form.is_valid())
        self.assertIn("start_at", form.errors)


class RentalViewsTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="viewowner",
            email="viewowner@test.com",
            password="StrongPassword123!",
            phone="09121111117",
        )
        self.renter = User.objects.create_user(
            username="viewrenter",
            email="viewrenter@test.com",
            password="StrongPassword123!",
            phone="09122222228",
        )
        self.stranger = User.objects.create_user(
            username="viewstranger",
            email="viewstranger@test.com",
            password="StrongPassword123!",
            phone="09122222229",
        )
        self.category = Category.objects.create(name="موسیقی", slug="music")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="گیتار کلاسیک یاماها",
            description="صدای شفاف و عالی",
            condition=Item.Condition.LIKE_NEW,
            hourly_price=Decimal("30000"),
            daily_price=Decimal("150000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            neighborhood="گیشا",
            allow_pickup=True,
            allow_courier=True,
        )
        self.client = Client()

    def test_rental_request_requires_login(self):
        """Anonymous user is redirected to login page."""
        url = reverse("rentals:rental_request", kwargs={"item_id": self.item.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp.url)

    def test_rental_request_owner_redirected(self):
        """Item owner accessing rental_request is redirected with error."""
        self.client.force_login(self.owner)
        url = reverse("rentals:rental_request", kwargs={"item_id": self.item.pk})
        resp = self.client.get(url, follow=True)
        self.assertRedirects(resp, reverse("catalog:item_detail", kwargs={"pk": self.item.pk}))

    def test_rental_request_and_payment_flow(self):
        """Full end-to-end web flow: request -> pay -> receipt."""
        self.client.force_login(self.renter)

        # 1. GET rental_request page
        request_url = reverse("rentals:rental_request", kwargs={"item_id": self.item.pk})
        resp = self.client.get(request_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "گیتار کلاسیک یاماها")

        # 2. POST rental_request
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        post_data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.PICKUP,
            "delivery_address": "",
        }
        resp = self.client.post(request_url, data=post_data)
        rental = Rental.objects.filter(item=self.item, renter=self.renter).first()
        self.assertIsNotNone(rental)
        self.assertRedirects(resp, reverse("rentals:rental_pay", kwargs={"pk": rental.pk}))

        # 3. GET rental_pay page
        pay_url = reverse("rentals:rental_pay", kwargs={"pk": rental.pk})
        resp = self.client.get(pay_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "پیش‌فاکتور و پرداخت امانت")

        # 4. POST simulated payment
        resp = self.client.post(pay_url)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.CONFIRMED)
        self.assertTrue(rental.tracking_code.startswith("AMN-"))
        self.assertRedirects(resp, reverse("rentals:rental_receipt", kwargs={"pk": rental.pk}))

        # 5. GET receipt page
        receipt_url = reverse("rentals:rental_receipt", kwargs={"pk": rental.pk})
        resp = self.client.get(receipt_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, rental.tracking_code)
        self.assertContains(resp, "تراکنش‌های پرداخت ثبت‌شده")

    def test_receipt_access_control(self):
        """Receipt is only viewable by renter, owner, or staff."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item,
            start_at=start,
            end_at=end,
        )
        simulate_payment(rental)
        receipt_url = reverse("rentals:rental_receipt", kwargs={"pk": rental.pk})

        # Stranger gets 403 Forbidden
        self.client.force_login(self.stranger)
        resp = self.client.get(receipt_url)
        self.assertEqual(resp.status_code, 403)

        # Owner gets 200 OK
        self.client.force_login(self.owner)
        resp = self.client.get(receipt_url)
        self.assertEqual(resp.status_code, 200)

        # Renter gets 200 OK
        self.client.force_login(self.renter)
        resp = self.client.get(receipt_url)
        self.assertEqual(resp.status_code, 200)


class HandoverLocationMapTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mapowner",
            email="mapowner@test.com",
            password="StrongPassword123!",
            phone="09121111118",
        )
        self.renter = User.objects.create_user(
            username="maprenter",
            email="maprenter@test.com",
            password="StrongPassword123!",
            phone="09122222230",
        )
        self.category = Category.objects.create(name="لوازم سفر", slug="travel-gear")
        self.item_with_coords = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="کوله پشتی کوهنوردی ۶۵ لیتری",
            description="مناسب صعودهای سنگین",
            condition=Item.Condition.NEW,
            daily_price=Decimal("90000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=True,
            latitude=Decimal("35.755000"),
            longitude=Decimal("51.405000"),
            address_text="میدان ونک، خیابان ملاصدرا",
        )
        self.item_no_coords = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="فلاسک استیل مسافرتی",
            description="نگهداری ۲۴ ساعته دمای آب",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("40000"),
            city="تهران",
            neighborhood="پونک",
            allow_pickup=True,
            allow_courier=True,
            latitude=None,
            longitude=None,
            address_text="پونک، میدان عدل",
        )
        self.client = Client()

    def test_form_courier_with_coordinates_valid(self):
        """Courier delivery with address and valid coordinates passes form validation."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.COURIER,
            "delivery_address": "تهران، خیابان آزادی، دانشگاه صنعتی شریف",
            "delivery_latitude": "35.702500",
            "delivery_longitude": "51.352100",
        }
        form = RentalRequestForm(data=data, item=self.item_with_coords, user=self.renter)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["delivery_latitude"], Decimal("35.702500"))
        self.assertEqual(form.cleaned_data["delivery_longitude"], Decimal("51.352100"))

    def test_form_courier_both_or_neither_lat_lng_validation(self):
        """Submitting only latitude without longitude fails both-or-neither constraint."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.COURIER,
            "delivery_address": "تهران، خیابان آزادی",
            "delivery_latitude": "35.702500",
            "delivery_longitude": "",
        }
        form = RentalRequestForm(data=data, item=self.item_with_coords, user=self.renter)
        self.assertFalse(form.is_valid())
        self.assertIn("مختصات جغرافیایی تحویل باید هر دو مشخص شوند یا هر دو خالی باشند.", form.non_field_errors())

    def test_form_courier_out_of_bounds_coordinates(self):
        """Latitude > 90 or longitude > 180 is rejected."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.COURIER,
            "delivery_address": "تهران، خیابان آزادی",
            "delivery_latitude": "95.000000",
            "delivery_longitude": "200.000000",
        }
        form = RentalRequestForm(data=data, item=self.item_with_coords, user=self.renter)
        self.assertFalse(form.is_valid())
        self.assertIn("delivery_latitude", form.errors)
        self.assertIn("delivery_longitude", form.errors)

    def test_form_pickup_clears_coordinates(self):
        """When delivery_method is pickup, any courier coordinates are cleared."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        data = {
            "start_at": start.strftime("%Y-%m-%dT%H:%M"),
            "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            "delivery_method": Rental.DeliveryMethod.PICKUP,
            "delivery_address": "",
            "delivery_latitude": "35.702500",
            "delivery_longitude": "51.352100",
        }
        form = RentalRequestForm(data=data, item=self.item_with_coords, user=self.renter)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["delivery_latitude"])
        self.assertIsNone(form.cleaned_data["delivery_longitude"])

    def test_receipt_shows_pickup_map_for_item_with_coords(self):
        """Pickup rental displays item's pickup location map on receipt."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item_with_coords,
            start_at=start,
            end_at=end,
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        simulate_payment(rental)

        self.client.force_login(self.renter)
        resp = self.client.get(reverse("rentals:rental_receipt", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "receipt-map-viewer")
        self.assertContains(resp, "موقعیت مکانی تحویل حضوری کالا (محل مالک)")
        self.assertContains(resp, "میدان ونک، خیابان ملاصدرا")

    def test_receipt_shows_courier_map_for_rental_with_coords(self):
        """Courier rental displays renter's delivery location map on receipt."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item_no_coords,
            start_at=start,
            end_at=end,
            delivery_method=Rental.DeliveryMethod.COURIER,
            delivery_address="خیابان ستارخان، کوچه مهدی",
            delivery_latitude=Decimal("35.715000"),
            delivery_longitude=Decimal("51.365000"),
        )
        simulate_payment(rental)

        self.client.force_login(self.renter)
        resp = self.client.get(reverse("rentals:rental_receipt", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "receipt-map-viewer")
        self.assertContains(resp, "موقعیت مکانی تحویل با پیک (مقصد متقاضی)")
        self.assertContains(resp, "خیابان ستارخان، کوچه مهدی")

    def test_receipt_shows_no_map_when_no_coords(self):
        """Rental with no coordinates shows address text but no map container."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item_no_coords,
            start_at=start,
            end_at=end,
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        simulate_payment(rental)

        self.client.force_login(self.renter)
        resp = self.client.get(reverse("rentals:rental_receipt", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "receipt-map-viewer")
        self.assertContains(resp, "پونک، میدان عدل")
