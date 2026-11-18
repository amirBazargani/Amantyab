"""Decorators for enforcing access permissions."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def verified_required(view_func):
    """
    Decorator for views that checks that the user is logged in and has verified their email.
    Staff and superusers bypass this check.
    If the user is not authenticated, redirects to the login page.
    If authenticated but unverified, redirects to accounts:profile with a warning message.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if not request.user.is_email_verified and not request.user.is_staff:
            messages.warning(
                request,
                "برای انجام این عملیات (ثبت کالا، درخواست اجاره یا ارسال پیام)، ابتدا باید آدرس ایمیل خود را تایید کنید.",
            )
            return redirect("accounts:profile")

        return view_func(request, *args, **kwargs)

    return _wrapped_view
