from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Category, Item, ItemImage


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("parent",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "category",
        "condition",
        "daily_price",
        "hourly_price",
        "deposit_amount",
        "city",
        "neighborhood",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
        "condition",
        "allow_pickup",
        "allow_courier",
        "category",
        "city",
    )
    search_fields = (
        "title",
        "description",
        "brand",
        "city",
        "neighborhood",
        "address_text",
        "owner__username",
        "owner__email",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "owner",
                    "category",
                    "title",
                    "description",
                    "brand",
                    "condition",
                    "is_active",
                )
            },
        ),
        (
            _("Pricing"),
            {
                "fields": (
                    "daily_price",
                    "hourly_price",
                    "deposit_amount",
                )
            },
        ),
        (
            _("Location & Delivery"),
            {
                "fields": (
                    "city",
                    "neighborhood",
                    "allow_pickup",
                    "allow_courier",
                    "address_text",
                    ("latitude", "longitude"),
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
    inlines = [ItemImageInline]


@admin.register(ItemImage)
class ItemImageAdmin(admin.ModelAdmin):
    list_display = ("item", "is_primary", "order", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("item__title",)
    readonly_fields = ("created_at",)
