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


