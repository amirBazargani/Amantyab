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

class ReviewFormTestCase(TestCase):
    def test_form_validation_valid(self):
        form = ReviewForm(data={"rating": 5, "comment": "عالی بود، کاملا سالم"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rating"], 5)

    def test_form_validation_rating_out_of_bounds(self):
        form_high = ReviewForm(data={"rating": 6, "comment": "بیش از ۵"})
        self.assertFalse(form_high.is_valid())
        self.assertIn("rating", form_high.errors)

        form_low = ReviewForm(data={"rating": 0, "comment": "کمتر از ۱"})
        self.assertFalse(form_low.is_valid())
        self.assertIn("rating", form_low.errors)

    def test_form_comment_optional(self):
        form = ReviewForm(data={"rating": 4, "comment": ""})
        self.assertTrue(form.is_valid())
