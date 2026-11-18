from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Item
from core.models import NotificationLog
from rentals.forms import DisputeForm, DisputeResolveForm, RentalRequestForm
from rentals.models import Dispute, Payment, Rental
from rentals.services import (
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


