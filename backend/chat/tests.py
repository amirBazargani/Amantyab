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

    def test_message_form_validation(self):
        form_valid = MessageForm(data={"body": "سلام و درود"})
        self.assertTrue(form_valid.is_valid())
        self.assertEqual(form_valid.cleaned_data["body"], "سلام و درود")

        form_empty = MessageForm(data={"body": "   "})
        self.assertFalse(form_empty.is_valid())


class ChatViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="vw_chat_owner",
            email="vw_owner@chat.test",
            password="Password123!",
            phone="09121111140",
        )
        self.renter = User.objects.create_user(
            username="vw_chat_renter",
            email="vw_renter@chat.test",
            password="Password123!",
            phone="09122222241",
        )
        self.stranger = User.objects.create_user(
            username="vw_chat_stranger",
            email="vw_stranger@chat.test",
            password="Password123!",
            phone="09123333342",
        )
        self.category = Category.objects.create(name="الکترونیک", slug="electronics")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="پروژکتور قابل حمل",
            description="پروژکتور فول اچ دی",
            daily_price=Decimal("250000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )

        self.conversation = Conversation.objects.create(
            item=self.item,
            renter=self.renter,
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("chat:inbox"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

        response = self.client.get(
            reverse("chat:start_conversation", kwargs={"item_pk": self.item.pk})
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(
            reverse("chat:conversation_detail", kwargs={"pk": self.conversation.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_owner_cannot_start_conversation_with_self(self):
        self.client.login(username="vw_chat_owner", password="Password123!")
        url = reverse("chat:start_conversation", kwargs={"item_pk": self.item.pk})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نمی‌توانید با خودتان درباره کالای خودتان گفتگو کنید")

    def test_renter_starts_conversation_successfully(self):
        self.client.login(username="vw_chat_renter", password="Password123!")
        url = reverse("chat:start_conversation", kwargs={"item_pk": self.item.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("chat:conversation_detail", kwargs={"pk": self.conversation.pk}),
        )

    def test_stranger_cannot_access_conversation_detail(self):
        self.client.login(username="vw_chat_stranger", password="Password123!")
        url = reverse("chat:conversation_detail", kwargs={"pk": self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_participants_can_access_and_exchange_messages(self):
        # 1. Renter opens conversation and sends first message
        self.client.login(username="vw_chat_renter", password="Password123!")
        url = reverse("chat:conversation_detail", kwargs={"pk": self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "پروژکتور قابل حمل")

        post_data = {"body": "سلام، فردا تحویل حضوری دارید؟"}
        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سلام، فردا تحویل حضوری دارید؟")

        msg = Message.objects.get(conversation=self.conversation)
        self.assertEqual(msg.sender, self.renter)
        self.assertFalse(msg.is_read)

        # 2. Owner checks inbox: should show 1 unread message
        self.client.login(username="vw_chat_owner", password="Password123!")
        inbox_resp = self.client.get(reverse("chat:inbox"))
        self.assertEqual(inbox_resp.status_code, 200)
        self.assertContains(inbox_resp, "پروژکتور قابل حمل")
        self.assertContains(inbox_resp, "سلام، فردا تحویل حضوری دارید؟")

        # 3. Owner opens conversation: incoming message is marked as read
        detail_resp = self.client.get(url)
        self.assertEqual(detail_resp.status_code, 200)
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

        # 4. Owner replies
        reply_data = {"body": "سلام، بله از ساعت ۱۰ صبح در خدمتتون هستم."}
        self.client.post(url, reply_data, follow=True)
        self.assertEqual(self.conversation.messages.count(), 2)

        # 5. Check order: messages are shown in chronological order
        msgs = list(self.conversation.messages.all())
        self.assertEqual(msgs[0].body, "سلام، فردا تحویل حضوری دارید؟")
        self.assertEqual(msgs[1].body, "سلام، بله از ساعت ۱۰ صبح در خدمتتون هستم.")
