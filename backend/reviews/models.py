from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        RENTER = "renter", _("Renter")

    rental = models.ForeignKey(
        "rentals.Rental",
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("rental"),
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="written_reviews",
        verbose_name=_("reviewer"),
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_reviews",
        verbose_name=_("reviewee"),
    )
    reviewee_role = models.CharField(
        _("reviewee role"),
        max_length=10,
        choices=Role.choices,
    )
    rating = models.PositiveSmallIntegerField(
        _("rating"),
        help_text=_("Rating score between 1 and 5"),
    )
    comment = models.TextField(_("comment"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_range_1_to_5",
            ),
            models.UniqueConstraint(
                fields=["rental", "reviewer"],
                name="unique_rental_reviewer_review",
            ),
        ]

    def __str__(self):
        return f"Review by {self.reviewer} for {self.reviewee} ({self.rating}/5)"

    def clean(self):
        super().clean()
        if not self.rental_id or not self.reviewer_id or not self.reviewee_id:
            return

        if self.rental.status != "completed":
            raise ValidationError(
                {"rental": _("Reviews can only be submitted for completed rentals.")}
            )

        if self.reviewer_id == self.reviewee_id:
            raise ValidationError(
                {"reviewee": _("A user cannot write a review for themselves.")}
            )

        rental_owner_id = self.rental.item.owner_id
        rental_renter_id = self.rental.renter_id
        valid_reviewers = {rental_owner_id, rental_renter_id}

        if self.reviewer_id not in valid_reviewers:
            raise ValidationError(
                {"reviewer": _("Reviewer must be either the owner or the renter of the item.")}
            )

        if self.reviewee_id not in valid_reviewers:
            raise ValidationError(
                {"reviewee": _("Reviewee must be either the owner or the renter of the item.")}
            )

        if self.reviewer_id == rental_owner_id:
            if self.reviewee_id != rental_renter_id:
                raise ValidationError(
                    {"reviewee": _("Owner must review the renter.")}
                )
            if self.reviewee_role != self.Role.RENTER:
                raise ValidationError(
                    {"reviewee_role": _("When reviewing the renter, role must be 'renter'.")}
                )
        elif self.reviewer_id == rental_renter_id:
            if self.reviewee_id != rental_owner_id:
                raise ValidationError(
                    {"reviewee": _("Renter must review the owner.")}
                )
            if self.reviewee_role != self.Role.OWNER:
                raise ValidationError(
                    {"reviewee_role": _("When reviewing the owner, role must be 'owner'.")}
                )
