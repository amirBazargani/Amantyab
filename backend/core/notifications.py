"""Notification dispatch service handling dual-channel Email and SMS deliveries."""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import NotificationLog
from .sms import get_sms_backend

logger = logging.getLogger("amanatyab.core")


def mask_phone(phone):
    """Mask phone number showing only the last 3 digits (e.g. 09123456789 -> ********789)."""
    if not phone:
        return ""
    clean = str(phone).strip()
    if len(clean) <= 3:
        return clean
    return "*" * (len(clean) - 3) + clean[-3:]


def mask_email(email):
    """Mask email address showing only the domain (e.g. user@example.com -> @example.com)."""
    if not email:
        return ""
    clean = str(email).strip()
    if "@" in clean:
        _, domain = clean.rsplit("@", 1)
        return f"@{domain}"
    return ""


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
    user_id = user.pk if user else None

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
        logger.info(
            "Notification attempt: event=%s channel=email user_id=%s status=skipped recipient=%s",
            event,
            user_id,
            mask_email(recipient_email),
        )
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
            logger.info(
                "Notification attempt: event=%s channel=email user_id=%s status=sent recipient=%s",
                event,
                user_id,
                mask_email(recipient_email),
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
            logger.warning(
                "Notification attempt: event=%s channel=email user_id=%s status=failed recipient=%s error=%s",
                event,
                user_id,
                mask_email(recipient_email),
                exc,
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
        logger.info(
            "Notification attempt: event=%s channel=sms user_id=%s status=skipped recipient=%s",
            event,
            user_id,
            mask_phone(recipient_phone),
        )
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
            logger.info(
                "Notification attempt: event=%s channel=sms user_id=%s status=sent recipient=%s",
                event,
                user_id,
                mask_phone(recipient_phone),
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
            logger.warning(
                "Notification attempt: event=%s channel=sms user_id=%s status=failed recipient=%s error=%s",
                event,
                user_id,
                mask_phone(recipient_phone),
                exc,
            )
        logs.append(sms_log)

    return logs
