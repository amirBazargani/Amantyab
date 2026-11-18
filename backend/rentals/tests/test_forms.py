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


