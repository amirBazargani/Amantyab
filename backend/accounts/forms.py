from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()

INPUT_CSS_CLASS = (
    "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
)


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
        required=False,
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
            "phone": forms.TextInput(attrs={"class": INPUT_CSS_CLASS, "dir": "ltr"}),
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
