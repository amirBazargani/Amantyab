import math
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Payment, Rental


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
