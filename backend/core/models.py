from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationLog(models.Model):
    """Store audit log of notification attempts via email and SMS."""

    CHANNEL_CHOICES = (
        ("email", _("Email")),
        ("sms", _("SMS")),
    )

    EVENT_CHOICES = (
        ("signup_confirmation", _("Signup Confirmation")),
        ("item_registered", _("Item Registered")),
        ("rental_ending_soon", _("Rental Ending Soon")),
    )

    STATUS_CHOICES = (
        ("sent", _("Sent")),
        ("failed", _("Failed")),
        ("skipped", _("Skipped")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("user"),
    )
    channel = models.CharField(
        _("channel"),
        max_length=10,
        choices=CHANNEL_CHOICES,
    )
    event = models.CharField(
        _("event"),
        max_length=50,
        choices=EVENT_CHOICES,
    )
    recipient = models.CharField(
        _("recipient"),
        max_length=255,
    )
    subject = models.CharField(
        _("subject"),
        max_length=255,
        blank=True,
    )
    body = models.TextField(
        _("body"),
    )
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=STATUS_CHOICES,
        default="sent",
    )
    error = models.TextField(
        _("error"),
        blank=True,
    )
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("item"),
    )
    rental = models.ForeignKey(
        "rentals.Rental",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("rental"),
    )
    created_at = models.DateTimeField(
        _("created at"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("notification log")
        verbose_name_plural = _("notification logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event", "created_at"]),
        ]

    def __str__(self):
        """Return readable summary of notification log."""
        return f"{self.channel} | {self.event} -> {self.recipient} ({self.status})"
