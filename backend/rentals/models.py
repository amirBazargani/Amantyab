from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class RentalQuerySet(models.QuerySet):
    def blocking(self):
        """Return non-cancelled rentals that block item availability."""
        return self.exclude(status=self.model.Status.CANCELLED)

    def overlapping(self, item=None, start=None, end=None):
        """
        Filter rentals overlapping a date range [start, end] and optionally for a specific item.
        Two intervals [s1, e1] and [s2, e2] overlap when s1 < e2 and e1 > s2.
        """
        qs = self
        if item is not None:
            if isinstance(item, (int, str)) and str(item).isdigit():
                qs = qs.filter(item_id=int(item))
            else:
                qs = qs.filter(item=item)
        if start is not None and end is not None:
            qs = qs.filter(start_at__lt=end, end_at__gt=start)
        elif start is not None:
            qs = qs.filter(end_at__gt=start)
        elif end is not None:
            qs = qs.filter(start_at__lt=end)
        return qs

    def for_renter(self, user):
        """Return rentals requested by the specified user as renter."""
        if not user:
            return self.none()
        return self.filter(renter=user)

    def for_owner(self, user):
        """Return rentals for items owned by the specified user."""
        if not user:
            return self.none()
        return self.filter(item__owner=user)

    def with_status(self, status):
        """Filter rentals by status or collection of statuses."""
        if not status:
            return self
        if isinstance(status, (list, tuple, set)):
            return self.filter(status__in=status)
        return self.filter(status=status)

    def ending_soon(self, hours=3):
        """
        Return handed_over rentals whose end_at is within now..now+hours
        and reminder_sent_at is null.
        """
        now = timezone.now()
        cutoff = now + timedelta(hours=int(hours))
        return self.filter(
            status=self.model.Status.HANDED_OVER,
            reminder_sent_at__isnull=True,
            end_at__gte=now,
            end_at__lte=cutoff,
        )


class Rental(models.Model):
    objects = RentalQuerySet.as_manager()

    class DeliveryMethod(models.TextChoices):
        PICKUP = "pickup", _("Pickup")
        COURIER = "courier", _("Courier")

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", _("Pending payment")
        CONFIRMED = "confirmed", _("Confirmed")
        HANDED_OVER = "handed_over", _("Handed over")
        RETURNED = "returned", _("Returned")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        DISPUTED = "disputed", _("Disputed")

    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.PROTECT,
        related_name="rentals",
        verbose_name=_("item"),
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rentals",
        verbose_name=_("renter"),
    )
    start_at = models.DateTimeField(_("start at"))
    end_at = models.DateTimeField(_("end at"))
    delivery_method = models.CharField(
        _("delivery method"),
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    rent_amount = models.DecimalField(
        _("rent amount"),
        max_digits=12,
        decimal_places=0,
    )
    deposit_amount = models.DecimalField(
        _("deposit amount"),
        max_digits=12,
        decimal_places=0,
        default=0,
    )
    commission_rate = models.DecimalField(
        _("commission rate"),
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.15"),
    )
    commission_amount = models.DecimalField(
        _("commission amount"),
        max_digits=12,
        decimal_places=0,
        default=0,
    )
    owner_payout = models.DecimalField(
        _("owner payout"),
        max_digits=12,
        decimal_places=0,
        default=0,
    )
    tracking_code = models.CharField(
        _("tracking code"),
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )
    delivery_address = models.TextField(_("delivery address"), blank=True)
    delivery_latitude = models.DecimalField(
        _("delivery latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90.0")),
            MaxValueValidator(Decimal("90.0")),
        ],
    )
    delivery_longitude = models.DecimalField(
        _("delivery longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180.0")),
            MaxValueValidator(Decimal("180.0")),
        ],
    )
    reminder_sent_at = models.DateTimeField(
        _("reminder sent at"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("rental")
        verbose_name_plural = _("rentals")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_at__gt=models.F("start_at")),
                name="rental_end_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(delivery_latitude__isnull=True) & models.Q(delivery_longitude__isnull=True))
                    | (models.Q(delivery_latitude__isnull=False) & models.Q(delivery_longitude__isnull=False))
                ),
                name="rental_delivery_lat_lng_both_or_neither",
            ),
        ]

    def __str__(self):
        item_title = getattr(self.item, "title", self.item_id)
        renter_name = getattr(self.renter, "username", self.renter_id)
        return f"Rental #{self.pk or 'new'} - {item_title} by {renter_name}"

    def clean(self):
        super().clean()

        if (self.delivery_latitude is None and self.delivery_longitude is not None) or (
            self.delivery_latitude is not None and self.delivery_longitude is None
        ):
            raise ValidationError(
                _(
                    "Delivery latitude and longitude must either both be set or both be empty."
                )
            )

        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError(
                {"end_at": _("End date and time must be after start date and time.")}
            )

        if hasattr(self, "item") and hasattr(self, "renter"):
            if self.item_id and self.renter_id and self.item.owner_id == self.renter_id:
                raise ValidationError(
                    {"renter": _("The owner cannot rent their own item.")}
                )

        if hasattr(self, "item") and self.item_id and self.start_at and self.end_at:
            overlapping_qs = (
                Rental.objects.blocking()
                .overlapping(item=self.item_id, start=self.start_at, end=self.end_at)
            )

            if self.pk:
                overlapping_qs = overlapping_qs.exclude(pk=self.pk)

            if overlapping_qs.exists():
                raise ValidationError(
                    _("This item is already booked for an overlapping time period.")
                )


class Payment(models.Model):
    class Kind(models.TextChoices):
        RENT = "rent", _("Rent")
        DEPOSIT = "deposit", _("Deposit")
        DEPOSIT_REFUND = "deposit_refund", _("Deposit refund")
        PAYOUT = "payout", _("Owner payout")

    class Status(models.TextChoices):
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")

    rental = models.ForeignKey(
        Rental,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("rental"),
    )
    kind = models.CharField(
        _("kind"),
        max_length=20,
        choices=Kind.choices,
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=0,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCESS,
    )
    receipt_no = models.CharField(
        _("receipt number"),
        max_length=64,
        unique=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.receipt_no} - {self.get_kind_display()} ({self.amount})"


class Dispute(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        RESOLVED = "resolved", _("Resolved")

    class DepositDecision(models.TextChoices):
        RETURN_TO_RENTER = "return_to_renter", _("Return to renter")
        GIVE_TO_OWNER = "give_to_owner", _("Give to owner")
        SPLIT = "split", _("Split")

    rental = models.ForeignKey(
        Rental,
        on_delete=models.PROTECT,
        related_name="disputes",
        verbose_name=_("rental"),
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_disputes",
        verbose_name=_("opened by"),
    )
    reason = models.TextField(_("reason"))
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    deposit_decision = models.CharField(
        _("deposit decision"),
        max_length=20,
        choices=DepositDecision.choices,
        blank=True,
    )
    resolution_note = models.TextField(_("resolution note"), blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_disputes",
        verbose_name=_("resolved by"),
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("dispute")
        verbose_name_plural = _("disputes")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dispute #{self.pk or 'new'} for Rental #{self.rental_id}"
