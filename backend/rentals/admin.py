from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Dispute, Payment, Rental


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("created_at",)


class DisputeInline(admin.StackedInline):
    model = Dispute
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "renter",
        "start_at",
        "end_at",
        "delivery_method",
        "status",
        "rent_amount",
        "deposit_amount",
        "created_at",
    )
    list_filter = (
        "status",
        "delivery_method",
        "created_at",
        "start_at",
    )
    search_fields = (
        "tracking_code",
        "item__title",
        "renter__username",
        "renter__email",
        "item__owner__username",
        "delivery_address",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "item",
                    "renter",
                    ("start_at", "end_at"),
                    "status",
                    "tracking_code",
                )
            },
        ),
        (
            _("Financials"),
            {
                "fields": (
                    "rent_amount",
                    "deposit_amount",
                    "commission_rate",
                    "commission_amount",
                    "owner_payout",
                )
            },
        ),
        (
            _("Delivery & Reminder"),
            {
                "fields": (
                    "delivery_method",
                    "delivery_address",
                    ("delivery_latitude", "delivery_longitude"),
                    "reminder_sent_at",
                )
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = [PaymentInline, DisputeInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_no",
        "rental",
        "kind",
        "amount",
        "status",
        "created_at",
    )
    list_filter = (
        "kind",
        "status",
        "created_at",
    )
    search_fields = (
        "receipt_no",
        "rental__tracking_code",
        "rental__item__title",
    )
    readonly_fields = ("created_at",)


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "rental",
        "opened_by",
        "status",
        "deposit_decision",
        "resolved_by",
        "resolved_at",
        "created_at",
    )
    list_filter = (
        "status",
        "deposit_decision",
        "created_at",
    )
    search_fields = (
        "rental__tracking_code",
        "opened_by__username",
        "reason",
        "resolution_note",
    )
    readonly_fields = ("created_at",)
