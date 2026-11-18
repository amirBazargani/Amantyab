from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Category, Item
from chat.forms import MessageForm
from chat.models import Conversation, Message

User = get_user_model()

class ChatFormTestCase(TestCase):
    def test_message_form_valid(self):
        form = MessageForm(data={"body": "سلام و درود"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["body"], "سلام و درود")

    def test_message_form_empty_body_invalid(self):
        form = MessageForm(data={"body": "   "})
        self.assertFalse(form.is_valid())
