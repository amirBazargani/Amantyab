import math
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Dispute, Payment, Rental


def calculate_price(item, start_at, end_at, commission_rate=Decimal("0.15")):
    """
    Calculate rental pricing based on item rates and duration according to docs/DOMAIN.md:
    duration < 24h and hourly_price set -> ceil(hours) * hourly_price
    else -> ceil(days) * daily_price
    commission = rent * rate
    owner_payout = rent - commission
    """
    if not start_at or not end_at:
        raise ValueError(_("Start and end date/time are required."))

    if end_at <= start_at:
        raise ValueError(_("End date/time must be strictly after start date/time."))

    duration = end_at - start_at
    total_seconds = Decimal(str(duration.total_seconds()))
    hours_float = float(total_seconds / Decimal("3600"))
    days_float = float(total_seconds / Decimal("86400"))

    # Duration < 24 hours and hourly_price is set
    if duration < timedelta(hours=24) and item.hourly_price is not None:
        pricing_type = "hourly"
        units_billed = max(1, math.ceil(hours_float))
        unit_price = Decimal(str(item.hourly_price))
        rent_amount = Decimal(units_billed) * unit_price
    else:
        pricing_type = "daily"
        units_billed = max(1, math.ceil(days_float))
        unit_price = Decimal(str(item.daily_price))
        rent_amount = Decimal(units_billed) * unit_price

    # Round currency to whole Tomans (0 decimal places)
    rent_amount = rent_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    commission_rate = Decimal(str(commission_rate))
    commission_amount = (rent_amount * commission_rate).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    owner_payout = rent_amount - commission_amount

    deposit_amount = Decimal(str(item.deposit_amount or 0)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    total_amount = rent_amount + deposit_amount

    return {
        "duration": duration,
        "hours_float": hours_float,
        "days_float": days_float,
        "pricing_type": pricing_type,
        "units_billed": units_billed,
        "unit_price": unit_price,
        "rent_amount": rent_amount,
        "deposit_amount": deposit_amount,
        "commission_rate": commission_rate,
        "commission_amount": commission_amount,
        "owner_payout": owner_payout,
        "total_amount": total_amount,
    }


def has_overlap(item, start_at, end_at, exclude_rental_id=None):
    """
    Check if the item already has a non-cancelled rental overlapping [start_at, end_at].
    Two intervals [s1, e1] and [s2, e2] overlap when s1 < e2 and e1 > s2.
    """
    if not item or not start_at or not end_at:
        return False

    qs = Rental.objects.filter(
        item=item,
        start_at__lt=end_at,
        end_at__gt=start_at,
    ).exclude(status=Rental.Status.CANCELLED)

    if exclude_rental_id:
        qs = qs.exclude(pk=exclude_rental_id)

    return qs.exists()


@transaction.atomic
def create_rental(
    *,
    renter,
    item,
    start_at,
    end_at,
    delivery_method=Rental.DeliveryMethod.PICKUP,
    delivery_address="",
    delivery_latitude=None,
    delivery_longitude=None,
    commission_rate=Decimal("0.15"),
):
    """
    Create a new Rental record in pending_payment status after validating
    business constraints (renter != owner, no overlap, price calculation).
    """
    if renter.pk == item.owner_id:
        raise ValidationError(_("Item owner cannot rent their own item."))

    if has_overlap(item, start_at, end_at):
        raise ValidationError(
            _("This item is already booked for an overlapping time period.")
        )

    price_info = calculate_price(
        item=item,
        start_at=start_at,
        end_at=end_at,
        commission_rate=commission_rate,
    )

    rental = Rental(
        item=item,
        renter=renter,
        start_at=start_at,
        end_at=end_at,
        delivery_method=delivery_method,
        delivery_address=delivery_address or "",
        delivery_latitude=delivery_latitude,
        delivery_longitude=delivery_longitude,
        status=Rental.Status.PENDING_PAYMENT,
        rent_amount=price_info["rent_amount"],
        deposit_amount=price_info["deposit_amount"],
        commission_rate=price_info["commission_rate"],
        commission_amount=price_info["commission_amount"],
        owner_payout=price_info["owner_payout"],
    )
    rental.full_clean()
    rental.save()
    return rental


def generate_tracking_code(rental):
    """Generate a readable, unique tracking code for confirmed rentals."""
    random_part = uuid.uuid4().hex[:6].upper()
    return f"AMN-{rental.pk:05d}-{random_part}"


def generate_receipt_no(kind, rental_pk):
    """Generate a unique receipt number for payments."""
    random_part = uuid.uuid4().hex[:8].upper()
    return f"RCP-{kind.upper()}-{rental_pk}-{random_part}"


@transaction.atomic
def simulate_payment(rental):
    """
    Simulate processing payment for a rental in pending_payment status:
    1. Verify current status is pending_payment.
    2. Create Payment row for rent.
    3. If deposit_amount > 0, create Payment row for deposit.
    4. Generate unique tracking code.
    5. Transition rental status to confirmed.
    Returns (rental, created_payments_list).
    """
    # Lock row for update
    rental = Rental.objects.select_for_update().get(pk=rental.pk)

    if rental.status != Rental.Status.PENDING_PAYMENT:
        raise ValidationError(
            _("Only rentals in pending payment status can be paid.")
        )

    created_payments = []

    # 1. Rent payment
    rent_payment = Payment.objects.create(
        rental=rental,
        kind=Payment.Kind.RENT,
        amount=rental.rent_amount,
        status=Payment.Status.SUCCESS,
        receipt_no=generate_receipt_no("rent", rental.pk),
    )
    created_payments.append(rent_payment)

    # 2. Deposit payment (if deposit amount > 0)
    if rental.deposit_amount > 0:
        deposit_payment = Payment.objects.create(
            rental=rental,
            kind=Payment.Kind.DEPOSIT,
            amount=rental.deposit_amount,
            status=Payment.Status.SUCCESS,
            receipt_no=generate_receipt_no("dep", rental.pk),
        )
        created_payments.append(deposit_payment)

    # 3. Update rental status and tracking code
    if not rental.tracking_code:
        rental.tracking_code = generate_tracking_code(rental)

    rental.status = Rental.Status.CONFIRMED
    rental.save(update_fields=["status", "tracking_code", "updated_at"])

    return rental, created_payments


ALLOWED_TRANSITIONS = {
    Rental.Status.PENDING_PAYMENT: [
        Rental.Status.CONFIRMED,
        Rental.Status.CANCELLED,
    ],
    Rental.Status.CONFIRMED: [
        Rental.Status.HANDED_OVER,
        Rental.Status.CANCELLED,
    ],
    Rental.Status.HANDED_OVER: [
        Rental.Status.RETURNED,
        Rental.Status.DISPUTED,
    ],
    Rental.Status.RETURNED: [
        Rental.Status.COMPLETED,
        Rental.Status.DISPUTED,
    ],
    Rental.Status.COMPLETED: [],
    Rental.Status.CANCELLED: [],
    Rental.Status.DISPUTED: [
        Rental.Status.COMPLETED,
    ],
}


def can_transition(rental, target_status, user):
    """
    Check whether `target_status` is a valid transition from `rental.status`
    and whether `user` is authorized to perform it.
    """
    if target_status not in ALLOWED_TRANSITIONS.get(rental.status, []):
        return False

    if not user or not user.is_authenticated:
        return False

    # Staff/admin can perform any valid transition
    if user.is_staff:
        return True

    # Check participant permissions per transition
    if target_status == Rental.Status.CONFIRMED:
        return user.pk == rental.renter_id

    if target_status == Rental.Status.CANCELLED:
        # Both renter and owner can cancel before handover
        return user.pk in (rental.renter_id, rental.item.owner_id)

    if target_status == Rental.Status.HANDED_OVER:
        # Owner confirms handing over the item to renter
        return user.pk == rental.item.owner_id

    if target_status == Rental.Status.RETURNED:
        # Renter marks item as returned
        return user.pk == rental.renter_id

    if target_status == Rental.Status.COMPLETED:
        # Owner confirms receiving back the item in good order
        return user.pk == rental.item.owner_id

    if target_status == Rental.Status.DISPUTED:
        # Either party can open a dispute
        return user.pk in (rental.renter_id, rental.item.owner_id)

    return False


def get_available_transitions(rental, user):
    """Return list of status values the user is allowed to transition the rental to."""
    if not user or not user.is_authenticated:
        return []
    allowed = []
    for next_status in ALLOWED_TRANSITIONS.get(rental.status, []):
        if can_transition(rental, next_status, user):
            allowed.append(next_status)
    return allowed


@transaction.atomic
def handover_rental(rental, user):
    """
    Transition rental from confirmed to handed_over.
    Only item owner (or staff) can perform this.
    """
    rental = Rental.objects.select_for_update().select_related("item").get(pk=rental.pk)

    if rental.status != Rental.Status.CONFIRMED:
        raise ValidationError(
            _("تحویل کالا فقط برای سفارش‌های در وضعیت تایید شده امکان‌پذیر است.")
        )

    if not can_transition(rental, Rental.Status.HANDED_OVER, user):
        raise PermissionDenied(
            _("تنها مالک کالا مجاز به تایید تحویل کالا می‌باشد.")
        )

    rental.status = Rental.Status.HANDED_OVER
    rental.save(update_fields=["status", "updated_at"])
    return rental


@transaction.atomic
def mark_returned_rental(rental, user):
    """
    Transition rental from handed_over to returned.
    Only renter (or staff) can perform this.
    """
    rental = Rental.objects.select_for_update().select_related("item").get(pk=rental.pk)

    if rental.status != Rental.Status.HANDED_OVER:
        raise ValidationError(
            _("اعلام بازگشت کالا فقط برای سفارش‌های تحویل‌داده‌شده امکان‌پذیر است.")
        )

    if not can_transition(rental, Rental.Status.RETURNED, user):
        raise PermissionDenied(
            _("تنها مستأجر مجاز به اعلام بازگرداندن کالا می‌باشد.")
        )

    rental.status = Rental.Status.RETURNED
    rental.save(update_fields=["status", "updated_at"])
    return rental


@transaction.atomic
def confirm_return_rental(rental, user):
    """
    Transition rental from returned to completed.
    Only item owner (or staff) can perform this.
    Creates deposit_refund Payment (if deposit_amount > 0)
    and payout Payment row for owner_payout.
    """
    rental = Rental.objects.select_for_update().select_related("item").get(pk=rental.pk)

    if rental.status != Rental.Status.RETURNED:
        raise ValidationError(
            _("تایید بازگشت و پایان سفارش فقط برای سفارش‌های بازگردانده‌شده امکان‌پذیر است.")
        )

    if not can_transition(rental, Rental.Status.COMPLETED, user):
        raise PermissionDenied(
            _("تنها مالک کالا مجاز به تایید استرداد و تکمیل اجاره می‌باشد.")
        )

    # 1. Deposit refund payment (if deposit > 0)
    if rental.deposit_amount > 0:
        already_refunded = rental.payments.filter(
            kind=Payment.Kind.DEPOSIT_REFUND,
            status=Payment.Status.SUCCESS,
        ).exists()
        if not already_refunded:
            Payment.objects.create(
                rental=rental,
                kind=Payment.Kind.DEPOSIT_REFUND,
                amount=rental.deposit_amount,
                status=Payment.Status.SUCCESS,
                receipt_no=generate_receipt_no("dep_ref", rental.pk),
            )

    # 2. Payout to owner
    if rental.owner_payout > 0:
        already_paid_out = rental.payments.filter(
            kind=Payment.Kind.PAYOUT,
            status=Payment.Status.SUCCESS,
        ).exists()
        if not already_paid_out:
            Payment.objects.create(
                rental=rental,
                kind=Payment.Kind.PAYOUT,
                amount=rental.owner_payout,
                status=Payment.Status.SUCCESS,
                receipt_no=generate_receipt_no("payout", rental.pk),
            )

    rental.status = Rental.Status.COMPLETED
    rental.save(update_fields=["status", "updated_at"])
    return rental


@transaction.atomic
def cancel_rental(rental, user):
    """
    Cancel rental before handover (from pending_payment or confirmed).
    Only renter, owner (or staff) can perform this.
    If confirmed and deposit_amount > 0, refunds deposit.
    """
    rental = Rental.objects.select_for_update().select_related("item").get(pk=rental.pk)

    if rental.status not in (Rental.Status.PENDING_PAYMENT, Rental.Status.CONFIRMED):
        raise ValidationError(
            _("امکان لغو سفارش پس از تحویل کالا وجود ندارد.")
        )

    if not can_transition(rental, Rental.Status.CANCELLED, user):
        raise PermissionDenied(
            _("شما دسترسی لازم برای لغو این سفارش را ندارید.")
        )

    # If already confirmed and deposit was collected, refund deposit
    if rental.status == Rental.Status.CONFIRMED and rental.deposit_amount > 0:
        already_refunded = rental.payments.filter(
            kind=Payment.Kind.DEPOSIT_REFUND,
            status=Payment.Status.SUCCESS,
        ).exists()
        if not already_refunded:
            Payment.objects.create(
                rental=rental,
                kind=Payment.Kind.DEPOSIT_REFUND,
                amount=rental.deposit_amount,
                status=Payment.Status.SUCCESS,
                receipt_no=generate_receipt_no("dep_ref", rental.pk),
            )

    rental.status = Rental.Status.CANCELLED
    rental.save(update_fields=["status", "updated_at"])
    return rental


@transaction.atomic
def open_dispute(rental, user, reason):
    """
    Open a dispute on an active rental (handed_over or returned).
    Only participants (renter or owner, or staff) can open.
    Transitions rental status to 'disputed' and creates Dispute record.
    """
    rental = Rental.objects.select_for_update().select_related("item", "item__owner", "renter").get(pk=rental.pk)

    if rental.status not in (Rental.Status.HANDED_OVER, Rental.Status.RETURNED):
        raise ValidationError(
            _("ثبت اختلاف تنها برای سفارش‌های در حال استفاده یا بازگردانده‌شده امکان‌پذیر است.")
        )

    if not can_transition(rental, Rental.Status.DISPUTED, user):
        raise PermissionDenied(
            _("شما مجاز به ثبت اختلاف برای این سفارش نمی‌باشید.")
        )

    if rental.disputes.filter(status=Dispute.Status.OPEN).exists():
        raise ValidationError(
            _("یک پرونده اختلاف فعال برای این سفارش در جریان است.")
        )

    dispute = Dispute.objects.create(
        rental=rental,
        opened_by=user,
        reason=reason,
        status=Dispute.Status.OPEN,
    )

    rental.status = Rental.Status.DISPUTED
    rental.save(update_fields=["status", "updated_at"])
    return dispute


@transaction.atomic
def resolve_dispute(dispute, admin_user, deposit_decision, resolution_note=""):
    """
    Admin resolves a dispute.
    Sets deposit_decision, creates matching Payment rows,
    marks dispute as resolved, and completes the rental.
    """
    dispute = (
        Dispute.objects.select_for_update()
        .select_related("rental", "rental__item", "rental__item__owner", "rental__renter")
        .get(pk=dispute.pk)
    )

    if not admin_user or not admin_user.is_staff:
        raise PermissionDenied(
            _("تنها مدیران سامانه مجاز به داوری و حل اختلاف هستند.")
        )

    if dispute.status != Dispute.Status.OPEN:
        raise ValidationError(
            _("این پرونده اختلاف قبلاً تعیین تکلیف و مختومه شده است.")
        )

    if deposit_decision not in Dispute.DepositDecision.values:
        raise ValidationError(
            _("تصمیم تعیین‌شده برای ودیعه نامعتبر است.")
        )

    rental = dispute.rental

    # 1. Handle deposit distribution according to deposit_decision
    if deposit_decision == Dispute.DepositDecision.RETURN_TO_RENTER:
        # Deposit refunded to renter
        if rental.deposit_amount > 0:
            already_refunded = rental.payments.filter(
                kind=Payment.Kind.DEPOSIT_REFUND,
                status=Payment.Status.SUCCESS,
            ).exists()
            if not already_refunded:
                Payment.objects.create(
                    rental=rental,
                    kind=Payment.Kind.DEPOSIT_REFUND,
                    amount=rental.deposit_amount,
                    status=Payment.Status.SUCCESS,
                    receipt_no=generate_receipt_no("dep_ref", rental.pk),
                )
    elif deposit_decision == Dispute.DepositDecision.GIVE_TO_OWNER:
        # Deposit given to owner as damage compensation
        if rental.deposit_amount > 0:
            Payment.objects.create(
                rental=rental,
                kind=Payment.Kind.PAYOUT,
                amount=rental.deposit_amount,
                status=Payment.Status.SUCCESS,
                receipt_no=generate_receipt_no("dep_own", rental.pk),
            )
    elif deposit_decision == Dispute.DepositDecision.SPLIT:
        # Split deposit between renter and owner (50-50)
        if rental.deposit_amount > 0:
            half_deposit = (rental.deposit_amount / Decimal("2")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            owner_deposit_share = rental.deposit_amount - half_deposit

            if half_deposit > 0:
                Payment.objects.create(
                    rental=rental,
                    kind=Payment.Kind.DEPOSIT_REFUND,
                    amount=half_deposit,
                    status=Payment.Status.SUCCESS,
                    receipt_no=generate_receipt_no("dep_ref", rental.pk),
                )

            if owner_deposit_share > 0:
                Payment.objects.create(
                    rental=rental,
                    kind=Payment.Kind.PAYOUT,
                    amount=owner_deposit_share,
                    status=Payment.Status.SUCCESS,
                    receipt_no=generate_receipt_no("dep_own", rental.pk),
                )

    # 2. Pay rent share to owner if not already paid
    if rental.owner_payout > 0:
        already_paid_out = rental.payments.filter(
            kind=Payment.Kind.PAYOUT,
            receipt_no__startswith="PAYOUT-",
            status=Payment.Status.SUCCESS,
        ).exists()
        if not already_paid_out:
            Payment.objects.create(
                rental=rental,
                kind=Payment.Kind.PAYOUT,
                amount=rental.owner_payout,
                status=Payment.Status.SUCCESS,
                receipt_no=generate_receipt_no("payout", rental.pk),
            )

    # 3. Update dispute record
    dispute.deposit_decision = deposit_decision
    dispute.resolution_note = resolution_note
    dispute.status = Dispute.Status.RESOLVED
    dispute.resolved_by = admin_user
    dispute.resolved_at = timezone.now()
    dispute.save(
        update_fields=[
            "deposit_decision",
            "resolution_note",
            "status",
            "resolved_by",
            "resolved_at",
        ]
    )

    # 4. Complete the rental
    rental.status = Rental.Status.COMPLETED
    rental.save(update_fields=["status", "updated_at"])

    return dispute


