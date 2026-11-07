import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import RegexValidator

User = get_user_model()

INPUT_CSS_CLASS = (
    "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
)

IRANIAN_PHONE_REGEX = r"^09\d{9}$"
phone_regex_validator = RegexValidator(
    regex=IRANIAN_PHONE_REGEX,
    message="شماره موبایل نامعتبر است. فرمت صحیح: ۰۹۱۲۳۴۵۶۷۸۹ (۱۱ رقم با ۰۹)",
)


def normalize_iranian_phone(phone_str):
    """Normalize Persian/Arabic digits, strip spaces/dashes, and standardize prefixes."""
    if not phone_str:
        return ""
    persian_arabic_digits = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
    english_digits = "01234567890123456789"
    trans_table = str.maketrans(persian_arabic_digits, english_digits)
    cleaned = str(phone_str).translate(trans_table)
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", cleaned)
    if cleaned.startswith("+98"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("0098"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("98") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]
    return cleaned


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label="ایمیل",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": INPUT_CSS_CLASS,
                "placeholder": "example@email.com",
                "dir": "ltr",
            }
        ),
    )
    first_name = forms.CharField(
        label="نام",
        required=False,
        widget=forms.TextInput(
            attrs={"class": INPUT_CSS_CLASS, "placeholder": "نام شما"}
        ),
    )
    last_name = forms.CharField(
        label="نام خانوادگی",
        required=False,
        widget=forms.TextInput(
            attrs={"class": INPUT_CSS_CLASS, "placeholder": "نام خانوادگی شما"}
        ),
    )
    phone = forms.CharField(
        label="شماره تماس",
        required=True,
        error_messages={
            "required": "وارد کردن شماره موبایل الزامی است.",
        },
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CSS_CLASS,
                "placeholder": "۰۹۱۲۳۴۵۶۷۸۹",
                "dir": "ltr",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "username" in self.fields:
            self.fields["username"].label = "نام کاربری"
            self.fields["username"].widget.attrs.update(
                {
                    "class": INPUT_CSS_CLASS,
                    "placeholder": "نام کاربری به انگلیسی",
                    "dir": "ltr",
                }
            )
        if "password1" in self.fields:
            self.fields["password1"].label = "رمز عبور"
            self.fields["password1"].widget.attrs.update(
                {
                    "class": INPUT_CSS_CLASS,
                    "placeholder": "حداقل ۸ کاراکتر",
                    "dir": "ltr",
                }
            )
        if "password2" in self.fields:
            self.fields["password2"].label = "تکرار رمز عبور"
            self.fields["password2"].widget.attrs.update(
                {
                    "class": INPUT_CSS_CLASS,
                    "placeholder": "تکرار رمز عبور",
                    "dir": "ltr",
                }
            )

    def clean_phone(self):
        raw_phone = self.cleaned_data.get("phone", "")
        phone = normalize_iranian_phone(raw_phone)
        if not phone:
            raise forms.ValidationError("وارد کردن شماره موبایل الزامی است.")
        if not re.match(IRANIAN_PHONE_REGEX, phone):
            raise forms.ValidationError(
                "شماره موبایل نامعتبر است. فرمت صحیح: ۰۹۱۲۳۴۵۶۷۸۹ (۱۱ رقم با ۰۹)"
            )
        return phone

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("این ایمیل قبلاً در سیستم ثبت شده است.")
        return email


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "نام کاربری یا رمز عبور وارد شده اشتباه است.",
        "inactive": "حساب کاربری شما غیرفعال شده است.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "username" in self.fields:
            self.fields["username"].label = "نام کاربری"
            self.fields["username"].widget.attrs.update(
                {
                    "class": INPUT_CSS_CLASS,
                    "placeholder": "نام کاربری",
                    "dir": "ltr",
                }
            )
        if "password" in self.fields:
            self.fields["password"].label = "رمز عبور"
            self.fields["password"].widget.attrs.update(
                {
                    "class": INPUT_CSS_CLASS,
                    "placeholder": "••••••••",
                    "dir": "ltr",
                }
            )


class ProfileForm(forms.ModelForm):
    phone = forms.CharField(
        label="شماره تماس",
        required=True,
        error_messages={
            "required": "وارد کردن شماره موبایل الزامی است.",
        },
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CSS_CLASS,
                "placeholder": "۰۹۱۲۳۴۵۶۷۸۹",
                "dir": "ltr",
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone",
            "city",
            "neighborhood",
            "bio",
        ]
        labels = {
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "phone": "شماره تماس",
            "city": "شهر",
            "neighborhood": "محله",
            "bio": "درباره من",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CSS_CLASS}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CSS_CLASS}),
            "city": forms.TextInput(
                attrs={"class": INPUT_CSS_CLASS, "placeholder": "مثال: تهران"}
            ),
            "neighborhood": forms.TextInput(
                attrs={"class": INPUT_CSS_CLASS, "placeholder": "مثال: ونک"}
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": (
                        "w-full px-3 py-2 border border-gray-300 rounded-lg "
                        "focus:outline-none focus:ring-2 focus:ring-blue-500 "
                        "focus:border-blue-500 text-sm"
                    ),
                    "rows": 4,
                    "placeholder": "چند کلمه درباره خودتان بنویسید...",
                }
            ),
        }

    def clean_phone(self):
        raw_phone = self.cleaned_data.get("phone", "")
        phone = normalize_iranian_phone(raw_phone)
        if not phone:
            raise forms.ValidationError("وارد کردن شماره موبایل الزامی است.")
        if not re.match(IRANIAN_PHONE_REGEX, phone):
            raise forms.ValidationError(
                "شماره موبایل نامعتبر است. فرمت صحیح: ۰۹۱۲۳۴۵۶۷۸۹ (۱۱ رقم با ۰۹)"
            )
        return phone
