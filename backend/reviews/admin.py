from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "rental",
        "reviewer",
        "reviewee",
        "reviewee_role",
        "rating",
        "created_at",
    )
    list_filter = ("rating", "reviewee_role", "created_at")
    search_fields = (
        "reviewer__username",
        "reviewer__email",
        "reviewee__username",
        "reviewee__email",
        "comment",
    )
    readonly_fields = ("created_at",)
