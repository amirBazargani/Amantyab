from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.forms import LoginForm, SignUpForm

User = get_user_model()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f"خوش آمدید {user.first_name or user.username}! حساب کاربری شما با موفقیت ایجاد شد.",
            )
            return redirect("core:home")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

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
            return redirect("core:home")
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



