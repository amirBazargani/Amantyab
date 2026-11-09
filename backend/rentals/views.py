from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _

from catalog.models import Item
from .forms import RentalRequestForm
from .models import Rental
from .services import (
    calculate_price,
    can_transition,
    cancel_rental,
    confirm_return_rental,
    create_rental,
    handover_rental,
    has_overlap,
    mark_returned_rental,
    simulate_payment,
)


@login_required
def rental_request(request, item_id):
    """
    Renter requests to rent an item. Validates dates, checks overlap,
    calculates prices and creates a pending_payment rental.
    """
    item = get_object_or_404(Item, pk=item_id, is_active=True)

    # Item owner cannot rent their own item
    if item.owner_id == request.user.pk:
        messages.error(
            request,
            _("شما مالک این کالا هستید و نمی‌توانید برای آن درخواست امانت ثبت کنید."),
        )
        return redirect("catalog:item_detail", pk=item.pk)

    if request.method == "POST":
        form = RentalRequestForm(request.POST, item=item, user=request.user)
        if form.is_valid():
            try:
                rental = create_rental(
                    renter=request.user,
                    item=item,
                    start_at=form.cleaned_data["start_at"],
                    end_at=form.cleaned_data["end_at"],
                    delivery_method=form.cleaned_data["delivery_method"],
                    delivery_address=form.cleaned_data.get("delivery_address", ""),
                    delivery_latitude=form.cleaned_data.get("delivery_latitude"),
                    delivery_longitude=form.cleaned_data.get("delivery_longitude"),
                )
                messages.success(
                    request,
                    _("درخواست امانت ثبت شد. لطفاً جهت نهایی‌سازی سفارش، پرداخت را تکمیل کنید."),
                )
                return redirect("rentals:rental_pay", pk=rental.pk)
            except ValidationError as e:
                form.add_error(None, e.messages[0] if hasattr(e, "messages") else str(e))
    else:
        form = RentalRequestForm(item=item, user=request.user)

    context = {
        "item": item,
        "form": form,
    }
    return render(request, "rentals/rental_request.html", context)


@login_required
def rental_pay(request, pk):
    """
    Checkout & simulated payment gateway page.
    Displays detailed price breakdown and allows confirming simulated payment.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
        renter=request.user,
    )

    # If already confirmed, go straight to receipt
    if rental.status == Rental.Status.CONFIRMED:
        return redirect("rentals:rental_receipt", pk=rental.pk)

    # If status is not pending_payment, cannot pay
    if rental.status != Rental.Status.PENDING_PAYMENT:
        messages.error(request, _("این سفارش در وضعیت پرداخت در انتظار نیست."))
        return redirect("catalog:item_detail", pk=rental.item_id)

    total_payable = rental.rent_amount + rental.deposit_amount

    if request.method == "POST":
        try:
            simulate_payment(rental)
            messages.success(
                request,
                _("پرداخت شبیه‌سازی‌شده با موفقیت انجام شد و امانت شما تایید گردید."),
            )
            return redirect("rentals:rental_receipt", pk=rental.pk)
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(
                request,
                _("خطایی در شبیه‌سازی پرداخت رخ داد: ") + str(e),
            )

    context = {
        "rental": rental,
        "item": rental.item,
        "total_payable": total_payable,
    }
    return render(request, "rentals/rental_pay.html", context)


@login_required
def rental_receipt(request, pk):
    """
    Shows official order receipt after successful payment,
    including tracking code, payment rows, and handover terms.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )

    # Only renter, owner, or staff can see receipt
    if request.user.pk not in (rental.renter_id, rental.item.owner_id) and not request.user.is_staff:
        raise PermissionDenied(_("شما دسترسی به فاکتور این سفارش را ندارید."))

    payments = rental.payments.order_by("created_at")
    total_paid = sum(p.amount for p in payments if p.status == p.Status.SUCCESS)

    context = {
        "rental": rental,
        "item": rental.item,
        "payments": payments,
        "total_paid": total_paid,
        "is_owner": request.user.pk == rental.item.owner_id,
        "is_renter": request.user.pk == rental.renter_id,
    }
    return render(request, "rentals/rental_receipt.html", context)


@login_required
def my_rentals(request):
    """
    List of rentals requested by the logged-in user as renter.
    Optional filter by status query param.
    """
    rentals = Rental.objects.filter(renter=request.user).select_related(
        "item", "item__owner"
    ).order_by("-created_at")

    selected_status = request.GET.get("status", "").strip()
    if selected_status and selected_status in Rental.Status.values:
        rentals = rentals.filter(status=selected_status)

    context = {
        "rentals": rentals,
        "selected_status": selected_status,
        "status_choices": Rental.Status.choices,
    }
    return render(request, "rentals/my_rentals.html", context)


@login_required
def owner_rentals(request):
    """
    List of rental requests for items owned by the logged-in user.
    Optional filter by status query param.
    """
    rentals = Rental.objects.filter(item__owner=request.user).select_related(
        "item", "renter"
    ).order_by("-created_at")

    selected_status = request.GET.get("status", "").strip()
    if selected_status and selected_status in Rental.Status.values:
        rentals = rentals.filter(status=selected_status)

    context = {
        "rentals": rentals,
        "selected_status": selected_status,
        "status_choices": Rental.Status.choices,
    }
    return render(request, "rentals/owner_rentals.html", context)


@login_required
def rental_detail(request, pk):
    """
    Detailed view of a rental for renter, owner, or staff.
    Shows item info, delivery info, payments, status timeline,
    and buttons for allowed lifecycle actions.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )

    if request.user.pk not in (rental.renter_id, rental.item.owner_id) and not request.user.is_staff:
        raise PermissionDenied(_("شما دسترسی به این سفارش را ندارید."))

    payments = rental.payments.order_by("created_at")
    total_paid = sum(p.amount for p in payments if p.status == p.Status.SUCCESS)

    reviews = list(rental.reviews.select_related("reviewer", "reviewee").all())
    has_reviewed = any(r.reviewer_id == request.user.pk for r in reviews)
    can_review = (
        rental.status == Rental.Status.COMPLETED
        and not has_reviewed
        and (request.user.pk in (rental.renter_id, rental.item.owner_id))
    )

    context = {
        "rental": rental,
        "item": rental.item,
        "payments": payments,
        "total_paid": total_paid,
        "reviews": reviews,
        "has_reviewed": has_reviewed,
        "can_review": can_review,
        "is_owner": request.user.pk == rental.item.owner_id,
        "is_renter": request.user.pk == rental.renter_id,
        "can_pay": rental.status == Rental.Status.PENDING_PAYMENT and (request.user.pk == rental.renter_id or request.user.is_staff),
        "can_handover": can_transition(rental, Rental.Status.HANDED_OVER, request.user),
        "can_mark_returned": can_transition(rental, Rental.Status.RETURNED, request.user),
        "can_confirm_return": can_transition(rental, Rental.Status.COMPLETED, request.user),
        "can_cancel": can_transition(rental, Rental.Status.CANCELLED, request.user),
    }
    return render(request, "rentals/rental_detail.html", context)


@login_required
@require_POST
def handover(request, pk):
    """
    Action: Owner confirms handing over the item to renter.
    Transitions from confirmed to handed_over.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )
    try:
        handover_rental(rental, request.user)
        messages.success(request, _("تحویل کالا به مستأجر با موفقیت تأیید شد."))
    except ValidationError as e:
        messages.error(request, e.messages[0] if hasattr(e, "messages") else str(e))
    except PermissionDenied as e:
        messages.error(request, str(e))

    return redirect("rentals:rental_detail", pk=rental.pk)


@login_required
@require_POST
def mark_returned(request, pk):
    """
    Action: Renter declares the item has been returned.
    Transitions from handed_over to returned.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )
    try:
        mark_returned_rental(rental, request.user)
        messages.success(request, _("اعلام بازگرداندن کالا ثبت شد و در انتظار تأیید موجر است."))
    except ValidationError as e:
        messages.error(request, e.messages[0] if hasattr(e, "messages") else str(e))
    except PermissionDenied as e:
        messages.error(request, str(e))

    return redirect("rentals:rental_detail", pk=rental.pk)


@login_required
@require_POST
def confirm_return(request, pk):
    """
    Action: Owner confirms receipt of item and releases deposit.
    Transitions from returned to completed, creates deposit_refund and payout payments.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )
    try:
        confirm_return_rental(rental, request.user)
        messages.success(request, _("بازگشت کالا تأیید شد، ودیعه آزاد گردید و سفارش با موفقیت تکمیل شد."))
    except ValidationError as e:
        messages.error(request, e.messages[0] if hasattr(e, "messages") else str(e))
    except PermissionDenied as e:
        messages.error(request, str(e))

    return redirect("rentals:rental_detail", pk=rental.pk)


@login_required
@require_POST
def cancel(request, pk):
    """
    Action: Cancel rental before physical handover (pending_payment or confirmed).
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )
    try:
        cancel_rental(rental, request.user)
        messages.success(request, _("سفارش اجاره با موفقیت لغو شد."))
    except ValidationError as e:
        messages.error(request, e.messages[0] if hasattr(e, "messages") else str(e))
    except PermissionDenied as e:
        messages.error(request, str(e))

    return redirect("rentals:rental_detail", pk=rental.pk)

