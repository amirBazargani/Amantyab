from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("sender", "body", "is_read", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "renter", "get_owner", "created_at", "updated_at")
    search_fields = (
        "item__title",
        "renter__username",
        "renter__email",
        "item__owner__username",
        "item__owner__email",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]

    @admin.display(description=_("Owner"))
    def get_owner(self, obj):
        return obj.owner


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = (
        "sender__username",
        "sender__email",
        "body",
        "conversation__item__title",
    )
    readonly_fields = ("created_at",)
