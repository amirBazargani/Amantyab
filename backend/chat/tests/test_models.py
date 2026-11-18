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

class ChatModelAndFormTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="chat_owner",
            email="owner@chat.test",
            password="Password123!",
            phone="09121111120",
        )
        self.renter = User.objects.create_user(
            username="chat_renter",
            email="renter@chat.test",
            password="Password123!",
            phone="09122222221",
        )
        self.stranger = User.objects.create_user(
            username="chat_stranger",
            email="stranger@chat.test",
            password="Password123!",
            phone="09123333332",
        )
        self.category = Category.objects.create(name="کمپینگ", slug="camping")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="چادر کوهنوردی ۴ نفره",
            description="چادر ضدآب با کیفیت بالا",
            daily_price=Decimal("120000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )

    def test_conversation_creation(self):
        conv = Conversation(item=self.item, renter=self.renter)
        conv.full_clean()
        conv.save()
        self.assertEqual(conv.owner, self.owner)
        self.assertEqual(str(conv), f"Conversation: {self.renter} & {self.owner} ({self.item.title})")

    def test_conversation_owner_cannot_be_renter(self):
        conv = Conversation(item=self.item, renter=self.owner)
        with self.assertRaises(ValidationError) as ctx:
            conv.full_clean()
        self.assertIn("renter", ctx.exception.message_dict)

    def test_conversation_unique_item_renter(self):
        Conversation.objects.create(item=self.item, renter=self.renter)
        dup = Conversation(item=self.item, renter=self.renter)
        with self.assertRaises((IntegrityError, ValidationError)):
            dup.save()

    def test_message_creation_valid_participants(self):
        conv = Conversation.objects.create(item=self.item, renter=self.renter)

        # Renter sends message
        msg1 = Message(conversation=conv, sender=self.renter, body="سلام، چادر در آخر هفته موجود است؟")
        msg1.full_clean()
        msg1.save()

        # Owner replies
        msg2 = Message(conversation=conv, sender=self.owner, body="سلام، بله چادر آماده تحویل است.")
        msg2.full_clean()
        msg2.save()

        messages = list(conv.messages.all())
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)

    def test_message_rejected_for_stranger(self):
        conv = Conversation.objects.create(item=self.item, renter=self.renter)
        msg = Message(conversation=conv, sender=self.stranger, body="پیام مزاحم")
        with self.assertRaises(ValidationError) as ctx:
            msg.full_clean()
        self.assertIn("sender", ctx.exception.message_dict)

