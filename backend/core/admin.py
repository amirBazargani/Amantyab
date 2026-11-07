from django.contrib import admin

from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin configuration for NotificationLog model."""

    list_display = (
        "id",
        "event",
        "channel",
        "recipient",
        "status",
        "user",
        "created_at",
    )
    list_filter = (
        "channel",
        "event",
        "status",
        "created_at",
    )
    search_fields = (
        "recipient",
        "subject",
        "body",
        "error",
        "user__phone",
        "user__email",
        "user__username",
    )
    readonly_fields = ("created_at",)
