from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _

from catalog.models import Item
from .forms import DisputeForm, DisputeResolveForm, RentalRequestForm
from .models import Dispute, Payment, Rental
from .services import (
    calculate_price,
    can_transition,
    cancel_rental,
    confirm_return_rental,
    create_rental,
    handover_rental,
    has_overlap,
    mark_returned_rental,
    open_dispute,
    resolve_dispute,
    simulate_payment,
)


@login_required
def rental_request(request, item_id):
    """
    Renter requests to rent an item. Validates dates, checks overlap,
    calculates prices and creates a pending_payment rental.
    """
    item = get_object_or_404(Item.objects.active(), pk=item_id)

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
    Optional filter by status query param using RentalQuerySet.
    """
    rentals = Rental.objects.for_renter(request.user).select_related(
        "item", "item__owner"
    ).order_by("-created_at")

    selected_status = request.GET.get("status", "").strip()
    if selected_status and selected_status in Rental.Status.values:
        rentals = rentals.with_status(selected_status)

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
    Optional filter by status query param using RentalQuerySet.
    """
    rentals = Rental.objects.for_owner(request.user).select_related(
        "item", "renter"
    ).order_by("-created_at")

    selected_status = request.GET.get("status", "").strip()
    if selected_status and selected_status in Rental.Status.values:
        rentals = rentals.with_status(selected_status)

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

    active_dispute = rental.disputes.filter(status=Dispute.Status.OPEN).first()
    disputes = list(rental.disputes.select_related("opened_by", "resolved_by").order_by("-created_at"))
    can_dispute = can_transition(rental, Rental.Status.DISPUTED, request.user) and not active_dispute

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
        "can_dispute": can_dispute,
        "active_dispute": active_dispute,
        "disputes": disputes,
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


@login_required
def dispute_open(request, pk):
    """
    Allow renter or owner (or staff) to open a dispute
    when rental is in handed_over or returned status.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )

    if request.user.pk not in (rental.renter_id, rental.item.owner_id) and not request.user.is_staff:
        raise PermissionDenied(_("شما مجاز به ثبت اختلاف برای این سفارش نمی‌باشید."))

    if rental.status not in (Rental.Status.HANDED_OVER, Rental.Status.RETURNED):
        messages.error(
            request,
            _("ثبت اختلاف تنها برای سفارش‌های در حال استفاده یا بازگردانده‌شده امکان‌پذیر است."),
        )
        return redirect("rentals:rental_detail", pk=rental.pk)

    if rental.disputes.filter(status=Dispute.Status.OPEN).exists():
        messages.warning(
            request,
            _("یک پرونده اختلاف فعال برای این سفارش در جریان است."),
        )
        return redirect("rentals:rental_detail", pk=rental.pk)

    if request.method == "POST":
        form = DisputeForm(request.POST)
        if form.is_valid():
            try:
                open_dispute(rental, request.user, form.cleaned_data["reason"])
                messages.success(
                    request,
                    _("اختلاف با موفقیت ثبت شد و پرونده جهت رسیدگی به مدیر سامانه ارجاع داده شد."),
                )
                return redirect("rentals:rental_detail", pk=rental.pk)
            except (ValidationError, PermissionDenied) as e:
                messages.error(request, e.messages[0] if hasattr(e, "messages") else str(e))
    else:
        form = DisputeForm()

    context = {
        "rental": rental,
        "item": rental.item,
        "form": form,
    }
    return render(request, "rentals/dispute_open.html", context)


@login_required
def admin_dashboard(request):
    """
    Staff-only dashboard showing platform overview and counts:
    users, items, rentals by status, total commission, and disputes.
    """
    if not request.user.is_staff:
        raise PermissionDenied(_("تنها مدیران سامانه مجاز به دسترسی به این بخش می‌باشند."))

    User = get_user_model()
    users_count = User.objects.count()
    items_count = Item.objects.count()
    active_items_count = Item.objects.active().count()
    total_rentals = Rental.objects.count()

    rentals_by_status = {
        status: Rental.objects.with_status(status).count()
        for status, _ in Rental.Status.choices
    }

    # Total commission from completed rentals
    total_commission = (
        Rental.objects.with_status(Rental.Status.COMPLETED).aggregate(
            total=Sum("commission_amount")
        )["total"]
        or Decimal("0")
    )

    open_disputes_count = Dispute.objects.filter(status=Dispute.Status.OPEN).count()
    resolved_disputes_count = Dispute.objects.filter(status=Dispute.Status.RESOLVED).count()
    total_disputes_count = Dispute.objects.count()

    recent_rentals = Rental.objects.select_related("item", "renter").order_by("-created_at")[:6]
    recent_disputes = Dispute.objects.select_related("rental", "opened_by").order_by("-created_at")[:6]

    context = {
        "users_count": users_count,
        "items_count": items_count,
        "active_items_count": active_items_count,
        "total_rentals": total_rentals,
        "rentals_by_status": rentals_by_status,
        "status_choices": Rental.Status.choices,
        "total_commission": total_commission,
        "open_disputes_count": open_disputes_count,
        "resolved_disputes_count": resolved_disputes_count,
        "total_disputes_count": total_disputes_count,
        "recent_rentals": recent_rentals,
        "recent_disputes": recent_disputes,
    }
    return render(request, "rentals/admin_dashboard.html", context)


@login_required
def admin_dispute_list(request):
    """
    Staff-only view to list and filter all disputes.
    """
    if not request.user.is_staff:
        raise PermissionDenied(_("تنها مدیران سامانه مجاز به دسترسی به این بخش می‌باشند."))

    status_filter = request.GET.get("status", "").strip()
    disputes_qs = Dispute.objects.select_related(
        "rental",
        "rental__item",
        "rental__item__owner",
        "rental__renter",
        "opened_by",
        "resolved_by",
    ).order_by("-created_at")

    if status_filter in Dispute.Status.values:
        disputes_qs = disputes_qs.filter(status=status_filter)

    open_count = Dispute.objects.filter(status=Dispute.Status.OPEN).count()
    resolved_count = Dispute.objects.filter(status=Dispute.Status.RESOLVED).count()
    total_count = Dispute.objects.count()

    context = {
        "disputes": disputes_qs,
        "status_filter": status_filter,
        "open_count": open_count,
        "resolved_count": resolved_count,
        "total_count": total_count,
    }
    return render(request, "rentals/admin_dispute_list.html", context)


@login_required
def admin_dispute_resolve(request, pk):
    """
    Staff-only view to review dispute details and resolve with a deposit decision.
    Creates matching payment rows and completes the rental.
    """
    if not request.user.is_staff:
        raise PermissionDenied(_("تنها مدیران سامانه مجاز به دسترسی به این بخش می‌باشند."))

    dispute = get_object_or_404(
        Dispute.objects.select_related(
            "rental",
            "rental__item",
            "rental__item__owner",
            "rental__renter",
            "opened_by",
            "resolved_by",
        ),
        pk=pk,
    )
    rental = dispute.rental

    if request.method == "POST":
        if dispute.status != Dispute.Status.OPEN:
            messages.error(request, _("این پرونده قبلاً تعیین تکلیف و مختومه شده است."))
            return redirect("rentals:admin_dispute_list")

        form = DisputeResolveForm(request.POST, instance=dispute)
        if form.is_valid():
            try:
                resolve_dispute(
                    dispute,
                    request.user,
                    form.cleaned_data["deposit_decision"],
                    form.cleaned_data["resolution_note"],
                )
                messages.success(
                    request,
                    _("پرونده اختلاف با موفقیت داوری و مختومه شد و تراکنش‌های مربوطه صادر گردید."),
                )
                return redirect("rentals:admin_dispute_list")
            except (ValidationError, PermissionDenied) as e:
                messages.error(request, e.messages[0] if hasattr(e, "messages") else str(e))
    else:
        form = DisputeResolveForm(instance=dispute)

    payments = rental.payments.order_by("created_at")

    context = {
        "dispute": dispute,
        "rental": rental,
        "form": form,
        "payments": payments,
    }
    return render(request, "rentals/admin_dispute_resolve.html", context)


