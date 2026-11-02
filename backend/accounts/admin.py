from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            _("Profile Info"),
            {
                "fields": (
                    "phone",
                    "city",
                    "neighborhood",
                    "bio",
                    "is_email_verified",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            _("Profile Info"),
            {
                "fields": (
                    "email",
                    "phone",
                    "city",
                    "neighborhood",
                    "bio",
                    "is_email_verified",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "phone",
        "city",
        "neighborhood",
        "is_email_verified",
        "is_staff",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "is_email_verified",
        "city",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
        "city",
        "neighborhood",
    )
