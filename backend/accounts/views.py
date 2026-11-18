import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.forms import LoginForm, ProfileForm, SignUpForm
from accounts.tokens import generate_verification_token, verify_token
from core.notifications import notify
from reviews.models import Review

logger = logging.getLogger("amanatyab.accounts")
security_logger = logging.getLogger("amanatyab.security")

User = get_user_model()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            logger.info("New user registered: user_id=%s username=%s", user.pk, user.username)
            login(request, user)
            token = generate_verification_token(user)
            verification_url = request.build_absolute_uri(
                reverse("accounts:verify_email", kwargs={"token": token})
            )
            notify(user, "signup_confirmation", context={"verification_url": verification_url})
            messages.success(
                request,
                f"خوش آمدید {user.first_name or user.username}! حساب کاربری شما ایجاد شد. لینک تایید ایمیل برای شما ارسال گردید.",
            )
            return redirect("accounts:profile")
        else:
            logger.warning("Signup validation failed for username=%s", request.POST.get("username", ""))
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    redirect_to = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            security_logger.info(
                "Login successful: user_id=%s username=%s ip=%s",
                user.pk,
                user.username,
                request.META.get("REMOTE_ADDR"),
            )
            remember_me = form.cleaned_data.get("remember_me", False)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(None)
            messages.success(
                request,
                f"خوش آمدید، {user.first_name or user.username}!",
            )
            if redirect_to and url_has_allowed_host_and_scheme(
                redirect_to, allowed_hosts={request.get_host()}
            ):
                return redirect(redirect_to)
            return redirect("accounts:profile")
        else:
            security_logger.warning(
                "Login failed: username=%s ip=%s",
                request.POST.get("username", ""),
                request.META.get("REMOTE_ADDR"),
            )
            messages.error(request, "نام کاربری یا رمز عبور اشتباه است.")
    else:
        form = LoginForm(request)

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": redirect_to},
    )


def logout_view(request):
    if request.user.is_authenticated:
        logger.info("User logged out: user_id=%s username=%s", request.user.pk, request.user.username)
    else:
        logger.info("Anonymous logout attempted")
    logout(request)
    messages.info(request, "شما با موفقیت از حساب کاربری خود خارج شدید.")
    return redirect("core:home")


@login_required
def profile_edit_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            logger.info("Profile updated: user_id=%s username=%s", request.user.pk, request.user.username)
            messages.success(request, "اطلاعات پروفایل شما با موفقیت ذخیره شد.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile_edit.html", {"form": form})


def public_profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    items = (
        profile_user.items.active()
        .prefetch_related("images")
        .order_by("-created_at")
    )

    received_reviews = (
        Review.objects.for_user(profile_user)
        .select_related("reviewer", "rental", "rental__item")
        .order_by("-created_at")
    )
    overall_avg = received_reviews.average_rating()
    owner_avg = received_reviews.for_user(profile_user, role=Review.Role.OWNER).average_rating()
    renter_avg = received_reviews.for_user(profile_user, role=Review.Role.RENTER).average_rating()

    return render(
        request,
        "accounts/profile_detail.html",
        {
            "profile_user": profile_user,
            "items": items,
            "received_reviews": received_reviews,
            "overall_avg": round(overall_avg, 1) if overall_avg else None,
            "owner_avg": round(owner_avg, 1) if owner_avg else None,
            "renter_avg": round(renter_avg, 1) if renter_avg else None,
            "review_count": received_reviews.count(),
        },
    )


def verify_email(request, token):
    """Verify user's email address using a signed token."""
    user, error_code = verify_token(token)
    if error_code == "expired":
        logger.warning("Email verification link expired: ip=%s", request.META.get("REMOTE_ADDR"))
        messages.error(
            request,
            "لینک تایید ایمیل منقضی شده است (اعتبار لینک‌ها ۲۴ ساعت است). لطفاً مجدداً درخواست ارسال لینک تایید دهید.",
        )
        return render(
            request,
            "accounts/verify_sent.html",
            {"status": "expired", "user": request.user if request.user.is_authenticated else None},
            status=400,
        )
    elif error_code or not user:
        security_logger.warning(
            "Email verification failed (invalid token): ip=%s",
            request.META.get("REMOTE_ADDR"),
        )
        messages.error(
            request,
            "لینک تایید ایمیل نامعتبر است یا مخدوش شده است.",
        )
        return render(
            request,
            "accounts/verify_sent.html",
            {"status": "invalid", "user": request.user if request.user.is_authenticated else None},
            status=400,
        )

    if user.is_email_verified:
        logger.info("User email already verified: user_id=%s", user.pk)
        messages.info(request, "ایمیل شما قبلاً تایید شده است.")
    else:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        logger.info("Email verified: user_id=%s username=%s email=%s", user.pk, user.username, user.email)
        security_logger.info(
            "Email verification success: user_id=%s email=%s ip=%s",
            user.pk,
            user.email,
            request.META.get("REMOTE_ADDR"),
        )
        messages.success(
            request,
            "ایمیل شما با موفقیت تایید شد! اکنون می‌توانید کالا ثبت کنید، اجاره دهید یا درخواست اجاره و پیام ارسال نمایید.",
        )

    if request.user.is_authenticated:
        return redirect("accounts:profile")
    return redirect("accounts:login")


@login_required
def resend_verification(request):
    """Resend email verification link to authenticated user."""
    if request.user.is_email_verified:
        messages.info(request, "ایمیل شما قبلاً تایید شده است.")
        return redirect("accounts:profile")

    if not request.user.email:
        messages.error(request, "حساب کاربری شما فاقد آدرس ایمیل است. لطفاً ابتدا در پروفایل ایمیل خود را ثبت کنید.")
        return redirect("accounts:profile")

    if request.method == "POST":
        token = generate_verification_token(request.user)
        verification_url = request.build_absolute_uri(
            reverse("accounts:verify_email", kwargs={"token": token})
        )
        subject = "تایید آدرس ایمیل — امانت‌یاب"
        body = render_to_string(
            "emails/verify.txt",
            {"user": request.user, "verification_url": verification_url},
        ).strip()

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "info@amanatyab.ir"),
                recipient_list=[request.user.email],
                fail_silently=False,
            )
            logger.info("Verification email resent: user_id=%s email=%s", request.user.pk, request.user.email)
            messages.success(request, f"لینک تایید جدید به آدرس {request.user.email} ارسال شد.")
        except Exception as exc:
            logger.warning("Failed to resend verification email: user_id=%s error=%s", request.user.pk, exc)
            messages.error(request, "خطا در ارسال ایمیل تایید. لطفاً لحظاتی بعد مجدداً تلاش کنید.")

        return render(request, "accounts/verify_sent.html", {"user": request.user, "resent": True})

    return render(request, "accounts/verify_sent.html", {"user": request.user, "resent": False})

