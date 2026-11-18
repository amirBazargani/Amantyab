import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from rentals.models import Rental
from .forms import ReviewForm
from .models import Review

logger = logging.getLogger("amanatyab.reviews")


@login_required
def review_create(request, rental_pk):
    """
    Create a review for a completed rental.
    Allowed only for renter (reviewing owner) or owner (reviewing renter),
    and strictly once per side.
    """
    rental = get_object_or_404(
        Rental.objects.select_related("item", "item__owner", "renter"),
        pk=rental_pk,
    )

    is_renter = request.user == rental.renter
    is_owner = request.user == rental.item.owner

    if not is_renter and not is_owner:
        logger.warning(
            "Permission denied on review create: rental_id=%s user_id=%s",
            rental.pk,
            request.user.pk,
        )
        raise PermissionDenied(_("شما اجازه دسترسی به این سفارش را ندارید."))

    if rental.status != Rental.Status.COMPLETED:
        logger.warning(
            "Review creation attempted on incomplete rental: rental_id=%s status=%s user_id=%s",
            rental.pk,
            rental.status,
            request.user.pk,
        )
        messages.error(
            request,
            _("تنها پس از پایان و تکمیل فرایند امانت امکان ثبت نظر و امتیاز وجود دارد."),
        )
        return redirect("rentals:rental_detail", pk=rental.pk)

    if Review.objects.filter(rental=rental, reviewer=request.user).exists():
        logger.warning(
            "Duplicate review attempt: rental_id=%s user_id=%s",
            rental.pk,
            request.user.pk,
        )
        messages.warning(
            request,
            _("شما قبلاً نظر و امتیاز خود را برای این سفارش ثبت کرده‌اید."),
        )
        return redirect("rentals:rental_detail", pk=rental.pk)

    if is_renter:
        reviewee = rental.item.owner
        reviewee_role = Review.Role.OWNER
    else:
        reviewee = rental.renter
        reviewee_role = Review.Role.RENTER

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.rental = rental
            review.reviewer = request.user
            review.reviewee = reviewee
            review.reviewee_role = reviewee_role
            try:
                review.full_clean()
                review.save()
                logger.info(
                    "Review created: review_id=%s rental_id=%s reviewer_id=%s reviewee_id=%s rating=%s role=%s",
                    review.pk,
                    rental.pk,
                    request.user.pk,
                    reviewee.pk,
                    review.rating,
                    reviewee_role,
                )
                messages.success(request, _("نظر و امتیاز شما با موفقیت ثبت شد."))
                return redirect("rentals:rental_detail", pk=rental.pk)
            except ValidationError as err:
                form.add_error(None, err)
    else:
        form = ReviewForm()

    context = {
        "rental": rental,
        "item": rental.item,
        "reviewee": reviewee,
        "reviewee_role": reviewee_role,
        "form": form,
    }
    return render(request, "reviews/review_form.html", context)
