"""Notification dispatch service handling dual-channel Email and SMS deliveries."""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import NotificationLog
from .sms import get_sms_backend


def notify(user, event, context=None, *, item=None, rental=None):
    """Render notification templates and send notifications via Email and SMS."""
    ctx = {
        "user": user,
        "item": item,
        "rental": rental,
    }
    if context:
        ctx.update(context)

    # 1. Render notification subject and body templates safely
    try:
        subject = render_to_string(f"notifications/{event}_subject.txt", ctx).strip()
    except Exception as exc:
        subject = f"Notification: {event}"

    try:
        body = render_to_string(f"notifications/{event}_body.txt", ctx).strip()
    except Exception as exc:
        body = f"Notification event: {event}"

    logs = []

    # 2. Process Email Channel
    recipient_email = getattr(user, "email", None) if user else None
    if not recipient_email:
        email_log = NotificationLog.objects.create(
            user=user,
            channel="email",
            event=event,
            recipient="",
            subject=subject,
            body=body,
            status="skipped",
            error="User has no email address.",
            item=item,
            rental=rental,
        )
        logs.append(email_log)
    else:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "info@amanatyab.ir"),
                recipient_list=[recipient_email],
                fail_silently=False,
            )
            email_log = NotificationLog.objects.create(
                user=user,
                channel="email",
                event=event,
                recipient=recipient_email,
                subject=subject,
                body=body,
                status="sent",
                item=item,
                rental=rental,
            )
        except Exception as exc:
            email_log = NotificationLog.objects.create(
                user=user,
                channel="email",
                event=event,
                recipient=recipient_email,
                subject=subject,
                body=body,
                status="failed",
                error=str(exc),
                item=item,
                rental=rental,
            )
        logs.append(email_log)

    # 3. Process SMS Channel
    recipient_phone = getattr(user, "phone", None) if user else None
    if not recipient_phone:
        sms_log = NotificationLog.objects.create(
            user=user,
            channel="sms",
            event=event,
            recipient="",
            subject=subject,
            body=body,
            status="skipped",
            error="User has no phone number.",
            item=item,
            rental=rental,
        )
        logs.append(sms_log)
    else:
        try:
            sms_backend = get_sms_backend()
            sms_backend.send_sms(recipient_phone, body)
            sms_log = NotificationLog.objects.create(
                user=user,
                channel="sms",
                event=event,
                recipient=recipient_phone,
                subject=subject,
                body=body,
                status="sent",
                item=item,
                rental=rental,
            )
        except Exception as exc:
            sms_log = NotificationLog.objects.create(
                user=user,
                channel="sms",
                event=event,
                recipient=recipient_phone,
                subject=subject,
                body=body,
                status="failed",
                error=str(exc),
                item=item,
                rental=rental,
            )
        logs.append(sms_log)

    return logs
