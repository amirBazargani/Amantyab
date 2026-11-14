from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Item
from core.models import NotificationLog
from .forms import DisputeForm, DisputeResolveForm, RentalRequestForm
from .models import Dispute, Payment, Rental
from .services import (
    calculate_price,
    can_transition,
    cancel_rental,
    confirm_return_rental,
    create_rental,
    get_available_transitions,
    handover_rental,
    has_overlap,
    mark_returned_rental,
    open_dispute,
    resolve_dispute,
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


class RentalLifecycleTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="item_owner",
            email="owner@test.ir",
            password="Password123!",
            phone="09121112233",
        )
        self.renter = User.objects.create_user(
            username="item_renter",
            email="renter@test.ir",
            password="Password123!",
            phone="09129998877",
        )
        self.stranger = User.objects.create_user(
            username="stranger_user",
            email="stranger@test.ir",
            password="Password123!",
            phone="09123334455",
        )
        self.staff_user = User.objects.create_user(
            username="admin_user",
            email="admin@test.ir",
            password="Password123!",
            phone="09120000000",
            is_staff=True,
        )
        self.category = Category.objects.create(name="ابزار برقی", slug="power-tools")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="اره فارسی بر ماکیتا",
            description="اره دقیق نجاری",
            condition=Item.Condition.LIKE_NEW,
            daily_price=Decimal("200000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            allow_courier=True,
        )

    def _create_confirmed_rental(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item,
            start_at=start,
            end_at=end,
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        simulate_payment(rental)
        rental.refresh_from_db()
        return rental

    def test_can_transition_matrix(self):
        """Test allowed transition checks for various actors and states."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item,
            start_at=start,
            end_at=end,
        )

        # pending_payment
        self.assertTrue(can_transition(rental, Rental.Status.CONFIRMED, self.renter))
        self.assertFalse(can_transition(rental, Rental.Status.CONFIRMED, self.owner))
        self.assertTrue(can_transition(rental, Rental.Status.CANCELLED, self.renter))
        self.assertTrue(can_transition(rental, Rental.Status.CANCELLED, self.owner))
        self.assertFalse(can_transition(rental, Rental.Status.CANCELLED, self.stranger))
        self.assertFalse(can_transition(rental, Rental.Status.HANDED_OVER, self.owner))

        # confirmed
        simulate_payment(rental)
        rental.refresh_from_db()
        self.assertTrue(can_transition(rental, Rental.Status.HANDED_OVER, self.owner))
        self.assertFalse(can_transition(rental, Rental.Status.HANDED_OVER, self.renter))
        self.assertFalse(can_transition(rental, Rental.Status.HANDED_OVER, self.stranger))
        self.assertTrue(can_transition(rental, Rental.Status.HANDED_OVER, self.staff_user))
        self.assertTrue(can_transition(rental, Rental.Status.CANCELLED, self.owner))
        self.assertTrue(can_transition(rental, Rental.Status.CANCELLED, self.renter))
        self.assertFalse(can_transition(rental, Rental.Status.COMPLETED, self.owner))

    def test_handover_transition(self):
        """Owner can handover confirmed rental; renter/stranger cannot."""
        rental = self._create_confirmed_rental()

        # Stranger cannot handover
        with self.assertRaises(PermissionDenied):
            handover_rental(rental, self.stranger)

        # Renter cannot handover
        with self.assertRaises(PermissionDenied):
            handover_rental(rental, self.renter)

        # Owner can handover
        handover_rental(rental, self.owner)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.HANDED_OVER)

        # Cannot handover again
        with self.assertRaises(ValidationError):
            handover_rental(rental, self.owner)

    def test_mark_returned_transition(self):
        """Renter can mark handed_over rental as returned; owner cannot."""
        rental = self._create_confirmed_rental()
        handover_rental(rental, self.owner)
        rental.refresh_from_db()

        # Owner cannot mark returned
        with self.assertRaises(PermissionDenied):
            mark_returned_rental(rental, self.owner)

        # Stranger cannot mark returned
        with self.assertRaises(PermissionDenied):
            mark_returned_rental(rental, self.stranger)

        # Renter marks returned
        mark_returned_rental(rental, self.renter)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.RETURNED)

        # Cannot mark returned again
        with self.assertRaises(ValidationError):
            mark_returned_rental(rental, self.renter)

    def test_confirm_return_creates_deposit_refund_and_payout(self):
        """Confirming return transitions to completed and creates deposit_refund + payout payments."""
        rental = self._create_confirmed_rental()
        handover_rental(rental, self.owner)
        mark_returned_rental(rental, self.renter)
        rental.refresh_from_db()

        # Renter cannot confirm return
        with self.assertRaises(PermissionDenied):
            confirm_return_rental(rental, self.renter)

        # Owner confirms return
        confirm_return_rental(rental, self.owner)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.COMPLETED)

        # Verify payments created
        refund_payment = Payment.objects.filter(
            rental=rental,
            kind=Payment.Kind.DEPOSIT_REFUND,
            status=Payment.Status.SUCCESS,
        ).first()
        self.assertIsNotNone(refund_payment)
        self.assertEqual(refund_payment.amount, rental.deposit_amount)

        payout_payment = Payment.objects.filter(
            rental=rental,
            kind=Payment.Kind.PAYOUT,
            status=Payment.Status.SUCCESS,
        ).first()
        self.assertIsNotNone(payout_payment)
        self.assertEqual(payout_payment.amount, rental.owner_payout)

        # Calling confirm_return on already completed rental raises ValidationError
        with self.assertRaises(ValidationError):
            confirm_return_rental(rental, self.owner)

    def test_cancel_pending_payment_no_refund_row(self):
        """Cancelling pending_payment rental does not create refund payments."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = create_rental(
            renter=self.renter,
            item=self.item,
            start_at=start,
            end_at=end,
        )

        cancel_rental(rental, self.renter)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.CANCELLED)
        self.assertEqual(rental.payments.count(), 0)

    def test_cancel_confirmed_creates_deposit_refund(self):
        """Cancelling confirmed rental creates deposit_refund payment for deposit amount."""
        rental = self._create_confirmed_rental()

        cancel_rental(rental, self.owner)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.CANCELLED)

        refund_payment = Payment.objects.filter(
            rental=rental,
            kind=Payment.Kind.DEPOSIT_REFUND,
            status=Payment.Status.SUCCESS,
        ).first()
        self.assertIsNotNone(refund_payment)
        self.assertEqual(refund_payment.amount, rental.deposit_amount)

    def test_cannot_cancel_after_handover(self):
        """Cannot cancel rental once item has been handed over."""
        rental = self._create_confirmed_rental()
        handover_rental(rental, self.owner)
        rental.refresh_from_db()

        with self.assertRaises(ValidationError):
            cancel_rental(rental, self.renter)

        with self.assertRaises(ValidationError):
            cancel_rental(rental, self.owner)

    def test_my_rentals_view(self):
        """my_rentals shows only current user's rentals as renter."""
        rental = self._create_confirmed_rental()
        client = Client()
        client.force_login(self.renter)

        resp = client.get(reverse("rentals:my_rentals"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "امانت‌های من")
        self.assertContains(resp, self.item.title)
        self.assertContains(resp, rental.tracking_code)

        # Owner looking at my_rentals should see empty
        client.force_login(self.owner)
        resp = client.get(reverse("rentals:my_rentals"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, rental.tracking_code)

    def test_owner_rentals_view(self):
        """owner_rentals shows rental requests on current user's items."""
        rental = self._create_confirmed_rental()
        client = Client()
        client.force_login(self.owner)

        resp = client.get(reverse("rentals:owner_rentals"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "درخواست‌های اجاره کالاهای من")
        self.assertContains(resp, self.item.title)
        self.assertContains(resp, rental.tracking_code)

        # Renter looking at owner_rentals should see empty
        client.force_login(self.renter)
        resp = client.get(reverse("rentals:owner_rentals"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, rental.tracking_code)

    def test_rental_detail_permissions_and_action_buttons(self):
        """rental_detail is protected and displays action buttons only to authorized parties."""
        rental = self._create_confirmed_rental()
        client = Client()

        # Stranger gets 403
        client.force_login(self.stranger)
        resp = client.get(reverse("rentals:rental_detail", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 403)

        # Owner sees handover button, but not return button
        client.force_login(self.owner)
        resp = client.get(reverse("rentals:rental_detail", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "تأیید تحویل کالا به مستأجر")
        self.assertNotContains(resp, "اعلام بازگرداندن کالا به موجر")

        # Renter does not see handover button
        client.force_login(self.renter)
        resp = client.get(reverse("rentals:rental_detail", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "تأیید تحویل کالا به مستأجر")

    def test_lifecycle_view_actions_post_endpoints(self):
        """POST endpoints for handover, mark_returned, confirm_return, cancel."""
        rental = self._create_confirmed_rental()
        client = Client()

        # 1. GET requests are rejected with 405 Method Not Allowed
        client.force_login(self.owner)
        resp = client.get(reverse("rentals:handover", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 405)

        # 2. Handover via POST by owner
        resp = client.post(reverse("rentals:handover", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 302)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.HANDED_OVER)

        # 3. Mark returned via POST by renter
        client.force_login(self.renter)
        resp = client.post(reverse("rentals:mark_returned", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 302)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.RETURNED)

        # 4. Confirm return via POST by owner
        client.force_login(self.owner)
        resp = client.post(reverse("rentals:confirm_return", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 302)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.COMPLETED)
        self.assertTrue(
            Payment.objects.filter(rental=rental, kind=Payment.Kind.DEPOSIT_REFUND).exists()
        )
        self.assertTrue(
            Payment.objects.filter(rental=rental, kind=Payment.Kind.PAYOUT).exists()
        )


class RentalDisputesAndAdminDashboardTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="disp_owner",
            email="disp_owner@test.com",
            password="StrongPassword123!",
            phone="09121111115",
        )
        self.renter = User.objects.create_user(
            username="disp_renter",
            email="disp_renter@test.com",
            password="StrongPassword123!",
            phone="09122222226",
        )
        self.other_user = User.objects.create_user(
            username="disp_other",
            email="disp_other@test.com",
            password="StrongPassword123!",
            phone="09123333337",
        )
        self.staff_admin = User.objects.create_user(
            username="disp_admin",
            email="disp_admin@test.com",
            password="StrongPassword123!",
            phone="09124444448",
            is_staff=True,
        )
        self.category = Category.objects.create(name="ابزار تست", slug="test-tools-disp")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="مینی فرز بوش",
            description="مینی فرز بسیار تمیز",
            condition=Item.Condition.LIKE_NEW,
            daily_price=Decimal("100000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            allow_pickup=True,
            allow_courier=True,
        )

    def _create_rental_in_status(self, status):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=2)
        rental = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=start,
            end_at=end,
            delivery_method=Rental.DeliveryMethod.PICKUP,
            status=status,
            rent_amount=Decimal("200000"),
            deposit_amount=Decimal("500000"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("30000"),
            owner_payout=Decimal("170000"),
            tracking_code=f"TRK-TEST-{status}",
        )
        # Create initial simulated payments
        Payment.objects.create(
            rental=rental,
            kind=Payment.Kind.RENT,
            amount=rental.rent_amount,
            status=Payment.Status.SUCCESS,
            receipt_no=f"RENT-{rental.pk}",
        )
        Payment.objects.create(
            rental=rental,
            kind=Payment.Kind.DEPOSIT,
            amount=rental.deposit_amount,
            status=Payment.Status.SUCCESS,
            receipt_no=f"DEP-{rental.pk}",
        )
        return rental

    def test_participant_can_open_dispute_on_handed_over_and_returned(self):
        """Participant (renter or owner) can open a dispute when rental is handed_over or returned."""
        client = Client()

        # 1. Renter opens dispute on handed_over rental
        rental_ho = self._create_rental_in_status(Rental.Status.HANDED_OVER)
        client.force_login(self.renter)
        resp = client.post(
            reverse("rentals:dispute_open", kwargs={"pk": rental_ho.pk}),
            {"reason": "دستگاه هنگام تحویل دارای نقص فنی بوده و کار نمی‌کند."},
        )
        self.assertEqual(resp.status_code, 302)
        rental_ho.refresh_from_db()
        self.assertEqual(rental_ho.status, Rental.Status.DISPUTED)
        dispute_ho = rental_ho.disputes.first()
        self.assertIsNotNone(dispute_ho)
        self.assertEqual(dispute_ho.opened_by, self.renter)
        self.assertEqual(dispute_ho.status, Dispute.Status.OPEN)

        # 2. Owner opens dispute on returned rental
        rental_ret = self._create_rental_in_status(Rental.Status.RETURNED)
        client.force_login(self.owner)
        resp = client.post(
            reverse("rentals:dispute_open", kwargs={"pk": rental_ret.pk}),
            {"reason": "قطعه جانبی مینی فرز مفقود شده و دستگاه کثیف بازگردانده شده است."},
        )
        self.assertEqual(resp.status_code, 302)
        rental_ret.refresh_from_db()
        self.assertEqual(rental_ret.status, Rental.Status.DISPUTED)
        dispute_ret = rental_ret.disputes.first()
        self.assertIsNotNone(dispute_ret)
        self.assertEqual(dispute_ret.opened_by, self.owner)
        self.assertEqual(dispute_ret.status, Dispute.Status.OPEN)

    def test_non_participant_cannot_open_dispute(self):
        """A user who is neither renter nor owner gets 403 on dispute_open."""
        client = Client()
        rental = self._create_rental_in_status(Rental.Status.HANDED_OVER)
        client.force_login(self.other_user)
        resp = client.get(reverse("rentals:dispute_open", kwargs={"pk": rental.pk}))
        self.assertEqual(resp.status_code, 403)

        resp = client.post(
            reverse("rentals:dispute_open", kwargs={"pk": rental.pk}),
            {"reason": "تلاش غیرمجاز برای ایجاد اختلاف توسط فرد ثالث."},
        )
        self.assertEqual(resp.status_code, 403)
        rental.refresh_from_db()
        self.assertEqual(rental.status, Rental.Status.HANDED_OVER)

    def test_cannot_open_dispute_on_invalid_status(self):
        """Cannot open dispute on confirmed, pending_payment, or completed rental."""
        client = Client()
        rental_conf = self._create_rental_in_status(Rental.Status.CONFIRMED)
        client.force_login(self.renter)
        resp = client.get(reverse("rentals:dispute_open", kwargs={"pk": rental_conf.pk}))
        # Redirected back to detail with error message
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("rentals:rental_detail", kwargs={"pk": rental_conf.pk}), resp.url)

        resp = client.post(
            reverse("rentals:dispute_open", kwargs={"pk": rental_conf.pk}),
            {"reason": "متن تستی برای وضعیت غیرمجاز"},
        )
        self.assertEqual(resp.status_code, 302)
        rental_conf.refresh_from_db()
        self.assertEqual(rental_conf.status, Rental.Status.CONFIRMED)

    def test_non_staff_forbidden_on_admin_pages(self):
        """Non-staff users get 403 on admin_dashboard, admin_dispute_list, and admin_dispute_resolve."""
        client = Client()
        rental = self._create_rental_in_status(Rental.Status.HANDED_OVER)
        dispute = open_dispute(rental, self.renter, "شکایت به علت شکستگی قاب دستگاه")

        # 1. Anonymous user redirected to login
        resp = client.get(reverse("rentals:admin_dashboard"))
        self.assertEqual(resp.status_code, 302)

        resp = client.get(reverse("rentals:admin_dispute_list"))
        self.assertEqual(resp.status_code, 302)

        resp = client.get(reverse("rentals:admin_dispute_resolve", kwargs={"pk": dispute.pk}))
        self.assertEqual(resp.status_code, 302)

        # 2. Authenticated non-staff gets 403 Forbidden
        client.force_login(self.renter)
        resp = client.get(reverse("rentals:admin_dashboard"))
        self.assertEqual(resp.status_code, 403)

        resp = client.get(reverse("rentals:admin_dispute_list"))
        self.assertEqual(resp.status_code, 403)

        resp = client.get(reverse("rentals:admin_dispute_resolve", kwargs={"pk": dispute.pk}))
        self.assertEqual(resp.status_code, 403)

        resp = client.post(
            reverse("rentals:admin_dispute_resolve", kwargs={"pk": dispute.pk}),
            {"deposit_decision": "return_to_renter", "resolution_note": "تلاش غیرمجاز"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_dispute_list_view(self):
        """Staff user can view dispute list and filter by status."""
        client = Client()
        rental1 = self._create_rental_in_status(Rental.Status.HANDED_OVER)
        disp1 = open_dispute(rental1, self.renter, "علت اختلاف اول برای تست")

        rental2 = self._create_rental_in_status(Rental.Status.RETURNED)
        disp2 = open_dispute(rental2, self.owner, "علت اختلاف دوم برای تست")
        resolve_dispute(disp2, self.staff_admin, Dispute.DepositDecision.RETURN_TO_RENTER, "حل شد")

        client.force_login(self.staff_admin)
        # All disputes
        resp = client.get(reverse("rentals:admin_dispute_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "پرونده‌های حل اختلاف و داوری")
        self.assertContains(resp, "علت اختلاف اول برای تست")
        self.assertContains(resp, "علت اختلاف دوم برای تست")

        # Open disputes filter
        resp_open = client.get(reverse("rentals:admin_dispute_list") + "?status=open")
        self.assertEqual(resp_open.status_code, 200)
        self.assertContains(resp_open, "علت اختلاف اول برای تست")
        self.assertNotContains(resp_open, "علت اختلاف دوم برای تست")

        # Resolved disputes filter
        resp_res = client.get(reverse("rentals:admin_dispute_list") + "?status=resolved")
        self.assertEqual(resp_res.status_code, 200)
        self.assertNotContains(resp_res, "علت اختلاف اول برای تست")
        self.assertContains(resp_res, "علت اختلاف دوم برای تست")

    def test_admin_dispute_resolve_return_to_renter(self):
        """Resolving with return_to_renter refunds deposit to renter and completes rental."""
        client = Client()
        rental = self._create_rental_in_status(Rental.Status.HANDED_OVER)
        dispute = open_dispute(rental, self.renter, "کالا معیوب تحویل شد و کار نمی‌کند.")

        client.force_login(self.staff_admin)
        resp = client.post(
            reverse("rentals:admin_dispute_resolve", kwargs={"pk": dispute.pk}),
            {
                "deposit_decision": Dispute.DepositDecision.RETURN_TO_RENTER,
                "resolution_note": "با توجه به ادعای مستند، کل ودیعه به مستأجر مسترد می‌گردد.",
            },
        )
        self.assertEqual(resp.status_code, 302)
        dispute.refresh_from_db()
        rental.refresh_from_db()

        self.assertEqual(dispute.status, Dispute.Status.RESOLVED)
        self.assertEqual(dispute.deposit_decision, Dispute.DepositDecision.RETURN_TO_RENTER)
        self.assertEqual(dispute.resolved_by, self.staff_admin)
        self.assertIsNotNone(dispute.resolved_at)
        self.assertEqual(rental.status, Rental.Status.COMPLETED)

        # Payments check: deposit_refund for renter, payout for owner
        refund = Payment.objects.filter(rental=rental, kind=Payment.Kind.DEPOSIT_REFUND).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, rental.deposit_amount)

        payout = Payment.objects.filter(rental=rental, kind=Payment.Kind.PAYOUT).first()
        self.assertIsNotNone(payout)
        self.assertEqual(payout.amount, rental.owner_payout)

    def test_admin_dispute_resolve_give_to_owner(self):
        """Resolving with give_to_owner pays deposit to owner as damage compensation."""
        client = Client()
        rental = self._create_rental_in_status(Rental.Status.RETURNED)
        dispute = open_dispute(rental, self.owner, "شکستگی موتور فرز به علت استفاده نادرست.")

        client.force_login(self.staff_admin)
        resp = client.post(
            reverse("rentals:admin_dispute_resolve", kwargs={"pk": dispute.pk}),
            {
                "deposit_decision": Dispute.DepositDecision.GIVE_TO_OWNER,
                "resolution_note": "خسارت وارده به دستگاه محرز است؛ ودیعه به موجر واگذار می‌شود.",
            },
        )
        self.assertEqual(resp.status_code, 302)
        dispute.refresh_from_db()
        rental.refresh_from_db()

        self.assertEqual(dispute.status, Dispute.Status.RESOLVED)
        self.assertEqual(dispute.deposit_decision, Dispute.DepositDecision.GIVE_TO_OWNER)
        self.assertEqual(rental.status, Rental.Status.COMPLETED)

        # Payments check: NO deposit_refund, deposit payout to owner + rent payout to owner
        self.assertFalse(Payment.objects.filter(rental=rental, kind=Payment.Kind.DEPOSIT_REFUND).exists())
        payouts = Payment.objects.filter(rental=rental, kind=Payment.Kind.PAYOUT)
        # Should have payout for deposit (500,000) and payout for rent (170,000)
        payout_amounts = sorted([p.amount for p in payouts])
        self.assertEqual(payout_amounts, [Decimal("170000"), Decimal("500000")])

    def test_admin_dispute_resolve_split(self):
        """Resolving with split divides deposit 50-50 between renter and owner."""
        client = Client()
        rental = self._create_rental_in_status(Rental.Status.RETURNED)
        dispute = open_dispute(rental, self.owner, "بخشی از متعلقات مفقود شده است.")

        client.force_login(self.staff_admin)
        resp = client.post(
            reverse("rentals:admin_dispute_resolve", kwargs={"pk": dispute.pk}),
            {
                "deposit_decision": Dispute.DepositDecision.SPLIT,
                "resolution_note": "توافق شد ودیعه ۵۰-۵۰ میان طرفین تسهیم گردد.",
            },
        )
        self.assertEqual(resp.status_code, 302)
        dispute.refresh_from_db()
        rental.refresh_from_db()

        self.assertEqual(dispute.status, Dispute.Status.RESOLVED)
        self.assertEqual(dispute.deposit_decision, Dispute.DepositDecision.SPLIT)
        self.assertEqual(rental.status, Rental.Status.COMPLETED)

        # Deposit was 500,000: renter gets 250,000 refund, owner gets 250,000 payout + 170,000 rent payout
        refund = Payment.objects.filter(rental=rental, kind=Payment.Kind.DEPOSIT_REFUND).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, Decimal("250000"))

        payouts = Payment.objects.filter(rental=rental, kind=Payment.Kind.PAYOUT)
        payout_amounts = sorted([p.amount for p in payouts])
        self.assertEqual(payout_amounts, [Decimal("170000"), Decimal("250000")])

    def test_admin_dashboard_metrics(self):
        """Admin dashboard displays accurate counts of users, items, rentals by status, and commission."""
        client = Client()
        client.force_login(self.staff_admin)

        # Create one completed rental with known commission
        completed_rental = self._create_rental_in_status(Rental.Status.COMPLETED)
        # Create one handed_over rental
        self._create_rental_in_status(Rental.Status.HANDED_OVER)

        resp = client.get(reverse("rentals:admin_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # Context assertions
        context = resp.context
        self.assertEqual(context["users_count"], User.objects.count())
        self.assertEqual(context["items_count"], Item.objects.count())
        self.assertEqual(context["total_rentals"], Rental.objects.count())
        self.assertIn("rentals_by_status", context)
        self.assertEqual(context["rentals_by_status"]["completed"], 1)
        self.assertEqual(context["rentals_by_status"]["handed_over"], 1)
        self.assertEqual(context["total_commission"], completed_rental.commission_amount)


class RentalQuerySetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="rq_owner", email="rq_owner@example.com", password="PassWord123!"
        )
        self.renter1 = User.objects.create_user(
            username="rq_renter1", email="rq_renter1@example.com", password="PassWord123!"
        )
        self.renter2 = User.objects.create_user(
            username="rq_renter2", email="rq_renter2@example.com", password="PassWord123!"
        )
        self.category = Category.objects.create(name="ابزار ساختمانی", slug="construction")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="تراز لیزری دیوالت",
            description="تراز لیزری ۳۶۰ درجه",
            condition=Item.Condition.LIKE_NEW,
            daily_price=Decimal("120000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            is_active=True,
        )

        now = timezone.now()
        # 1. Confirmed rental
        self.rental_confirmed = Rental.objects.create(
            item=self.item,
            renter=self.renter1,
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=3),
            status=Rental.Status.CONFIRMED,
            rent_amount=Decimal("240000"),
            deposit_amount=Decimal("50000"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("36000"),
            owner_payout=Decimal("204000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        # 2. Cancelled rental
        self.rental_cancelled = Rental.objects.create(
            item=self.item,
            renter=self.renter2,
            start_at=now + timedelta(days=1, hours=2),
            end_at=now + timedelta(days=2),
            status=Rental.Status.CANCELLED,
            rent_amount=Decimal("120000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("18000"),
            owner_payout=Decimal("102000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
        )
        # 3. Handed over rental ending soon (in 2 hours)
        self.rental_ending_soon = Rental.objects.create(
            item=self.item,
            renter=self.renter1,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(hours=2),
            status=Rental.Status.HANDED_OVER,
            rent_amount=Decimal("120000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("18000"),
            owner_payout=Decimal("102000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            reminder_sent_at=None,
        )
        # 4. Handed over rental ending later (in 24 hours)
        self.rental_ending_later = Rental.objects.create(
            item=self.item,
            renter=self.renter2,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(hours=24),
            status=Rental.Status.HANDED_OVER,
            rent_amount=Decimal("120000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("18000"),
            owner_payout=Decimal("102000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            reminder_sent_at=None,
        )

    def test_blocking(self):
        blocking = Rental.objects.blocking()
        self.assertIn(self.rental_confirmed, blocking)
        self.assertIn(self.rental_ending_soon, blocking)
        self.assertNotIn(self.rental_cancelled, blocking)

    def test_overlapping(self):
        now = timezone.now()
        # Overlaps rental_confirmed (days 1 to 3)
        overlap_qs = Rental.objects.overlapping(
            item=self.item,
            start=now + timedelta(days=1, hours=12),
            end=now + timedelta(days=2),
        )
        self.assertIn(self.rental_confirmed, overlap_qs)
        self.assertIn(self.rental_cancelled, overlap_qs)

        # Non-overlapping range
        no_overlap = Rental.objects.overlapping(
            item=self.item,
            start=now + timedelta(days=10),
            end=now + timedelta(days=12),
        )
        self.assertEqual(no_overlap.count(), 0)

    def test_for_renter(self):
        renter1_rentals = Rental.objects.for_renter(self.renter1)
        self.assertIn(self.rental_confirmed, renter1_rentals)
        self.assertIn(self.rental_ending_soon, renter1_rentals)
        self.assertNotIn(self.rental_cancelled, renter1_rentals)

    def test_for_owner(self):
        owner_rentals = Rental.objects.for_owner(self.owner)
        self.assertEqual(owner_rentals.count(), 4)

    def test_with_status(self):
        confirmed = Rental.objects.with_status(Rental.Status.CONFIRMED)
        self.assertIn(self.rental_confirmed, confirmed)
        self.assertNotIn(self.rental_cancelled, confirmed)

        multiple = Rental.objects.with_status([Rental.Status.CONFIRMED, Rental.Status.CANCELLED])
        self.assertEqual(multiple.count(), 2)

    def test_ending_soon(self):
        ending_soon_3h = Rental.objects.ending_soon(hours=3)
        self.assertIn(self.rental_ending_soon, ending_soon_3h)
        self.assertNotIn(self.rental_ending_later, ending_soon_3h)
        self.assertNotIn(self.rental_confirmed, ending_soon_3h)

        # Once reminder is sent, it is no longer returned
        self.rental_ending_soon.reminder_sent_at = timezone.now()
        self.rental_ending_soon.save()
        self.assertNotIn(self.rental_ending_soon, Rental.objects.ending_soon(hours=3))


class SendRentalRemindersCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="rem_owner",
            email="rem_owner@example.com",
            phone="09121111111",
            password="PassWord123!",
        )
        self.renter = User.objects.create_user(
            username="rem_renter",
            email="rem_renter@example.com",
            phone="09122222222",
            password="PassWord123!",
        )
        self.category = Category.objects.create(name="ابزار باغبانی", slug="gardening")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="چمن‌زن موتوری",
            description="چمن‌زن بنزینی پرقدرت",
            condition=Item.Condition.GOOD,
            daily_price=Decimal("180000"),
            city="تهران",
            neighborhood="ونک",
            allow_pickup=True,
            is_active=True,
        )

        now = timezone.now()
        # 1. Handed over rental ending in 2 hours (should get reminder with default 3 hours)
        self.rental_2h = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(hours=2),
            status=Rental.Status.HANDED_OVER,
            rent_amount=Decimal("180000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("27000"),
            owner_payout=Decimal("153000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            reminder_sent_at=None,
        )

        # 2. Handed over rental ending in 3 days (should NOT get reminder)
        self.rental_3d = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=3),
            status=Rental.Status.HANDED_OVER,
            rent_amount=Decimal("540000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("81000"),
            owner_payout=Decimal("459000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            reminder_sent_at=None,
        )

        # 3. Non-handed_over rental (confirmed) ending in 2 hours (should NOT get reminder)
        self.rental_confirmed = Rental.objects.create(
            item=self.item,
            renter=self.renter,
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(hours=2),
            status=Rental.Status.CONFIRMED,
            rent_amount=Decimal("180000"),
            deposit_amount=Decimal("0"),
            commission_rate=Decimal("0.15"),
            commission_amount=Decimal("27000"),
            owner_payout=Decimal("153000"),
            delivery_method=Rental.DeliveryMethod.PICKUP,
            reminder_sent_at=None,
        )

    def test_send_reminders_default_hours(self):
        out = StringIO()
        call_command("send_rental_reminders", stdout=out)
        output = out.getvalue()

        self.assertIn("Sent 1 reminder(s)", output)

        # 2-hour rental got updated
        self.rental_2h.refresh_from_db()
        self.assertIsNotNone(self.rental_2h.reminder_sent_at)

        # 3-day rental and confirmed rental are untouched
        self.rental_3d.refresh_from_db()
        self.assertIsNone(self.rental_3d.reminder_sent_at)
        self.rental_confirmed.refresh_from_db()
        self.assertIsNone(self.rental_confirmed.reminder_sent_at)

        # Notification logs were created for both email and sms
        logs = NotificationLog.objects.filter(rental=self.rental_2h, event="rental_ending_soon")
        self.assertEqual(logs.count(), 2)
        channels = set(logs.values_list("channel", flat=True))
        self.assertEqual(channels, {"email", "sms"})
        for log in logs:
            self.assertEqual(log.status, "sent")
            self.assertIn("چمن‌زن موتوری", log.body)

    def test_send_reminders_idempotent(self):
        # First call sends 1 reminder
        out1 = StringIO()
        call_command("send_rental_reminders", stdout=out1)
        self.assertIn("Sent 1 reminder(s)", out1.getvalue())

        # Second call sends 0 reminders
        out2 = StringIO()
        call_command("send_rental_reminders", stdout=out2)
        self.assertIn("Sent 0 reminder(s)", out2.getvalue())

    def test_send_reminders_custom_hours_argument(self):
        # With --hours 1, the 2-hour rental is NOT matched
        out = StringIO()
        call_command("send_rental_reminders", hours=1, stdout=out)
        self.assertIn("Sent 0 reminder(s)", out.getvalue())

        self.rental_2h.refresh_from_db()
        self.assertIsNone(self.rental_2h.reminder_sent_at)

        # With --hours 5, the 2-hour rental is matched and sent
        out2 = StringIO()
        call_command("send_rental_reminders", hours=5, stdout=out2)
        self.assertIn("Sent 1 reminder(s)", out2.getvalue())

        self.rental_2h.refresh_from_db()
        self.assertIsNotNone(self.rental_2h.reminder_sent_at)


