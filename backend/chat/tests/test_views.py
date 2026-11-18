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

class ChatViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="vw_chat_owner",
            email="vw_owner@chat.test",
            password="Password123!",
            phone="09121111140",
            is_email_verified=True,
        )
        self.renter = User.objects.create_user(
            username="vw_chat_renter",
            email="vw_renter@chat.test",
            password="Password123!",
            phone="09122222241",
            is_email_verified=True,
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




class ChatLoggingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="chat_log_owner",
            password="Password123!",
            phone="09121118800",
            email="co@example.com",
            is_email_verified=True,
        )
        self.renter = User.objects.create_user(
            username="chat_log_renter",
            password="Password123!",
            phone="09122229911",
            email="cr@example.com",
            is_email_verified=True,
        )
        self.third_party = User.objects.create_user(
            username="chat_log_third",
            password="Password123!",
            phone="09123330022",
            email="ct@example.com",
        )
        self.category = Category.objects.create(name="عکاسی", slug="photo")
        self.item = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="دوربین عکاسی سونی",
            daily_price=Decimal("150000"),
            deposit_amount=Decimal("1000000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )
        self.conversation = Conversation.objects.create(
            item=self.item,
            renter=self.renter,
        )

    def test_message_send_logs_without_message_body(self):
        self.client.force_login(self.renter)
        url = reverse("chat:conversation_detail", kwargs={"pk": self.conversation.pk})
        secret_text = "این متن محرمانه است و هرگز نباید در لاگ ظاهر شود"
        data = {"body": secret_text}

        with self.assertLogs("amanatyab.chat", level="INFO") as cm:
            resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Ensure "Message sent: ..." is logged
        self.assertTrue(
            any("Message sent: message_id=" in msg for msg in cm.output),
            f"Expected message sent log in {cm.output}",
        )
        # Ensure secret_text is NEVER in any log line
        for log_line in cm.output:
            self.assertNotIn(
                secret_text,
                log_line,
                "Message body MUST NOT be logged!",
            )

    def test_conversation_opened_logging(self):
        self.client.force_login(self.renter)
        item2 = Item.objects.create(
            owner=self.owner,
            category=self.category,
            title="لنز تله سونی",
            daily_price=Decimal("80000"),
            deposit_amount=Decimal("500000"),
            city="تهران",
            allow_pickup=True,
            is_active=True,
        )
        url = reverse("chat:start_conversation", kwargs={"item_pk": item2.pk})
        with self.assertLogs("amanatyab.chat", level="INFO") as cm:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            any("Conversation opened: conversation_id=" in msg for msg in cm.output),
            f"Expected conversation opened log in {cm.output}",
        )

    def test_permission_denied_warning_logging(self):
        self.client.force_login(self.third_party)
        url = reverse("chat:conversation_detail", kwargs={"pk": self.conversation.pk})
        with self.assertLogs("amanatyab.chat", level="WARNING") as cm:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            any("Permission denied on chat conversation" in msg for msg in cm.output),
            f"Expected permission warning in {cm.output}",
        )

