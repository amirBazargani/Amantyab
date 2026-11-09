from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from catalog.models import Item
from .forms import RentalRequestForm
from .models import Rental
from .services import calculate_price, create_rental, has_overlap, simulate_payment


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
