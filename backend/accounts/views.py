from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.forms import LoginForm, ProfileForm, SignUpForm
from core.notifications import notify
from reviews.models import Review

User = get_user_model()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            notify(user, "signup_confirmation")
            messages.success(
                request,
                f"خوش آمدید {user.first_name or user.username}! حساب کاربری شما با موفقیت ایجاد شد.",
            )
            return redirect("accounts:profile")
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
            messages.error(request, "نام کاربری یا رمز عبور اشتباه است.")
    else:
        form = LoginForm(request)

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": redirect_to},
    )


def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, "شما با موفقیت از حساب کاربری خود خارج شدید.")
        return redirect("core:home")
    # Also handle GET safely by redirecting
    logout(request)
    messages.info(request, "شما با موفقیت از حساب کاربری خود خارج شدید.")
    return redirect("core:home")


@login_required
def profile_edit_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
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
