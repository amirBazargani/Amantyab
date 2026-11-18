from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from core import sms
from core.models import NotificationLog
from core.notifications import mask_email, mask_phone, notify

User = get_user_model()


class NotificationServiceTests(TestCase):
    def setUp(self):
        sms.outbox.clear()
        self.user = User.objects.create_user(
            username="notif_user",
            email="notif_user@example.com",
            phone="09121112233",
            password="Password123!",
        )

    def tearDown(self):
        sms.outbox.clear()

    def test_mask_phone(self):
        self.assertEqual(mask_phone("09123456789"), "********789")
        self.assertEqual(mask_phone("123"), "123")
        self.assertEqual(mask_phone(""), "")
        self.assertEqual(mask_phone(None), "")

    def test_mask_email(self):
        self.assertEqual(mask_email("user@example.com"), "@example.com")
        self.assertEqual(mask_email("ali.reza@sub.amanatyab.ir"), "@sub.amanatyab.ir")
        self.assertEqual(mask_email(""), "")
        self.assertEqual(mask_email(None), "")
        self.assertEqual(mask_email("no_at_sign"), "")

    @override_settings(SMS_BACKEND="locmem")
    def test_notify_sent_to_locmem_email_and_sms_outboxes(self):
        logs = notify(self.user, "test_event", context={"custom_note": "سلام"})
        self.assertEqual(len(logs), 2)

        # 1. Email check via mail.outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["notif_user@example.com"])
        self.assertIn("test_event", sent_email.subject)

        # 2. SMS check via sms.outbox
        self.assertEqual(len(sms.outbox), 1)
        sent_sms = sms.outbox[0]
        self.assertEqual(sent_sms["phone"], "09121112233")
        self.assertIn("test_event", sent_sms["message"])

        # 3. NotificationLog check
        email_log = NotificationLog.objects.get(user=self.user, channel="email")
        sms_log = NotificationLog.objects.get(user=self.user, channel="sms")
        self.assertEqual(email_log.status, "sent")
        self.assertEqual(sms_log.status, "sent")
        self.assertEqual(sms_log.recipient, "09121112233")

    @override_settings(SMS_BACKEND="locmem")
    def test_notify_skipped_without_phone(self):
        user_no_phone = User.objects.create_user(
            username="nophone_user",
            email="nophone@example.com",
            phone="",
            password="Password123!",
        )
        logs = notify(user_no_phone, "test_event")
        self.assertEqual(len(logs), 2)

        # SMS is skipped
        self.assertEqual(len(sms.outbox), 0)
        sms_log = NotificationLog.objects.get(user=user_no_phone, channel="sms")
        self.assertEqual(sms_log.status, "skipped")
        self.assertIn("no phone", sms_log.error)

        # Email is still sent
        self.assertEqual(len(mail.outbox), 1)
        email_log = NotificationLog.objects.get(user=user_no_phone, channel="email")
        self.assertEqual(email_log.status, "sent")

    @override_settings(SMS_BACKEND="locmem")
    def test_failed_sms_backend_does_not_break_request(self):
        # Simulate SMS backend raising RuntimeError
        with patch.object(sms.LocmemBackend, "send_sms", side_effect=RuntimeError("SMS Gateway 503")):
            # Must not raise exception
            logs = notify(self.user, "test_event")

        self.assertEqual(len(logs), 2)
        sms_log = NotificationLog.objects.get(user=self.user, channel="sms")
        self.assertEqual(sms_log.status, "failed")
        self.assertIn("SMS Gateway 503", sms_log.error)

        # Email succeeded
        self.assertEqual(len(mail.outbox), 1)
        email_log = NotificationLog.objects.get(user=self.user, channel="email")
        self.assertEqual(email_log.status, "sent")

    def test_failed_email_backend_does_not_break_request(self):
        # Simulate send_mail raising SMTPException
        with patch("core.notifications.send_mail", side_effect=RuntimeError("SMTP Connection Refused")):
            logs = notify(self.user, "test_event")

        self.assertEqual(len(logs), 2)
        email_log = NotificationLog.objects.get(user=self.user, channel="email")
        self.assertEqual(email_log.status, "failed")
        self.assertIn("SMTP Connection Refused", email_log.error)

    def test_notify_logs_masked_recipients_and_never_logs_body(self):
        secret_content = "SUPER_SECRET_PAYLOAD_ABC_987"
        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            notify(self.user, "test_event", context={"secret": secret_content})

        output = " ".join(cm.output)
        self.assertIn("event=test_event", output)
        self.assertIn("channel=email", output)
        self.assertIn("channel=sms", output)
        self.assertIn(f"user_id={self.user.pk}", output)
        self.assertIn("status=sent", output)

        self.assertIn("********233", output)
        self.assertNotIn("09121112233", output)

        self.assertIn("@example.com", output)
        self.assertNotIn("notif_user@", output)

        self.assertNotIn(secret_content, output)
