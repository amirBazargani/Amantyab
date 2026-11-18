from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.forms import ItemForm
from catalog.models import Category, Item

User = get_user_model()


class ItemFormTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="formuser",
            email="formuser@example.com",
            password="StrongPassword123!",
        )
        self.category = Category.objects.create(name="ابزار برقی", slug="power-tools")

    def test_item_form_valid(self):
        form_data = {
            "title": "دریل چکشی رونیکس",
            "category": self.category.pk,
            "description": "توضیحات دریل با کیفیت",
            "condition": Item.Condition.LIKE_NEW,
            "daily_price": "80000",
            "deposit_amount": "200000",
            "city": "تهران",
            "neighborhood": "ونک",
            "allow_pickup": True,
            "allow_courier": True,
            "latitude": "35.750000",
            "longitude": "51.400000",
            "address_text": "میدان ونک",
        }
        form = ItemForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_item_form_requires_at_least_one_delivery_method(self):
        form_data = {
            "title": "دریل چکشی",
            "category": self.category.pk,
            "description": "توضیحات",
            "condition": Item.Condition.GOOD,
            "daily_price": "80000",
            "city": "تهران",
            "allow_pickup": False,
            "allow_courier": False,
        }
        form = ItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("حداقل باید یکی از روش‌های تحویل", str(form.non_field_errors()))

    def test_item_form_both_or_neither_lat_lng(self):
        # Lat without Lng
        form_data = {
            "title": "دریل چکشی",
            "category": self.category.pk,
            "description": "توضیحات",
            "condition": Item.Condition.GOOD,
            "daily_price": "80000",
            "city": "تهران",
            "allow_pickup": True,
            "latitude": "35.750000",
            "longitude": "",
        }
        form = ItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("مختصات جغرافیایی", str(form.non_field_errors()))

        # Lng without Lat
        form_data["latitude"] = ""
        form_data["longitude"] = "51.400000"
        form = ItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("مختصات جغرافیایی", str(form.non_field_errors()))

    def test_item_form_lat_lng_ranges(self):
        # Out of bounds lat
        form_data = {
            "title": "دریل چکشی",
            "category": self.category.pk,
            "description": "توضیحات",
            "condition": Item.Condition.GOOD,
            "daily_price": "80000",
            "city": "تهران",
            "allow_pickup": True,
            "latitude": "120.000000",
            "longitude": "51.400000",
        }
        form = ItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)

        # Out of bounds lng
        form_data["latitude"] = "35.000000"
        form_data["longitude"] = "195.000000"
        form = ItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("longitude", form.errors)
