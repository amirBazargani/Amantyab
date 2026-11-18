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

class RentalViewsTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="viewowner",
            email="viewowner@test.com",
            password="StrongPassword123!",
            phone="09121111117",
            is_email_verified=True,
        )
        self.renter = User.objects.create_user(
            username="viewrenter",
            email="viewrenter@test.com",
            password="StrongPassword123!",
            phone="09122222228",
            is_email_verified=True,
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




class RentalsLoggingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="r_owner",
            password="Password123!",
            phone="09121113355",
            email="ro@example.com",
        )
        self.renter = User.objects.create_user(
            username="r_renter",
            password="Password123!",
            phone="09122224466",
            email="rr@example.com",
        )
        self.admin = User.objects.create_user(
            username="r_admin",
            password="Password123!",
            phone="09129990000",
            email="admin@example.com",
            is_staff=True,
        )
        self.category = Category.objects.create(name="ابزار باغبانی", slug="garden")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="اره زنجیری بنزینی",
            daily_price=Decimal("120000"),
            deposit_amount=Decimal("400000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )

    def test_rental_lifecycle_logging(self):
        now = timezone.now()
        start = now + timedelta(days=1)
        end = now + timedelta(days=3)

        # 1. create_rental log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            rental = create_rental(
                renter=self.renter,
                item=self.item,
                start_at=start,
                end_at=end,
            )
        self.assertTrue(
            any("Rental request created: rental_id=" in msg for msg in cm.output),
            f"Expected create log in {cm.output}",
        )

        # 2. simulate_payment log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            rental, _ = simulate_payment(rental)
        self.assertTrue(
            any("Payment processed: rental_id=" in msg for msg in cm.output),
            f"Expected payment log in {cm.output}",
        )

        # 3. handover log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            rental = handover_rental(rental, self.owner)
        self.assertTrue(
            any("Rental handed over: rental_id=" in msg for msg in cm.output),
            f"Expected handover log in {cm.output}",
        )

        # 4. return log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            rental = mark_returned_rental(rental, self.renter)
        self.assertTrue(
            any("Rental returned: rental_id=" in msg for msg in cm.output),
            f"Expected return log in {cm.output}",
        )

        # 5. confirm return log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            rental = confirm_return_rental(rental, self.owner)
        self.assertTrue(
            any("Rental completed: rental_id=" in msg for msg in cm.output),
            f"Expected completion log in {cm.output}",
        )

    def test_cancel_rental_logging(self):
        now = timezone.now()
        rental = create_rental(
            renter=self.renter,
            item=self.item,
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=7),
        )
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            cancel_rental(rental, self.renter)
        self.assertTrue(
            any("Rental cancelled: rental_id=" in msg for msg in cm.output),
            f"Expected cancel log in {cm.output}",
        )

    def test_dispute_open_and_resolve_logging(self):
        now = timezone.now()
        rental = create_rental(
            renter=self.renter,
            item=self.item,
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=3),
        )
        rental, _ = simulate_payment(rental)
        rental = handover_rental(rental, self.owner)

        # 1. Dispute open log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            dispute = open_dispute(rental, self.renter, "خرابی اره زنجیری")
        self.assertTrue(
            any("Dispute opened: dispute_id=" in msg for msg in cm.output),
            f"Expected dispute open log in {cm.output}",
        )

        # 2. Dispute resolve log
        with self.assertLogs("amanatyab.rentals", level="INFO") as cm:
            resolve_dispute(
                dispute,
                self.admin,
                Dispute.DepositDecision.RETURN_TO_RENTER,
                "ودیعه عودت گردید",
            )
        self.assertTrue(
            any("Dispute resolved: dispute_id=" in msg for msg in cm.output),
            f"Expected dispute resolve log in {cm.output}",
        )

    def test_permission_denied_warning_logging(self):
        self.client.force_login(self.renter)
        # Non-staff accessing admin dashboard
        with self.assertLogs("amanatyab.rentals", level="WARNING") as cm:
            resp = self.client.get(reverse("rentals:admin_dashboard"))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            any("Permission denied on admin dashboard" in msg for msg in cm.output),
            f"Expected admin warning log in {cm.output}",
        )



