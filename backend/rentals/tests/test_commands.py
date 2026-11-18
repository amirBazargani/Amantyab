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


