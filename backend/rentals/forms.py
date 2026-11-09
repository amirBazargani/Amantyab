from datetime import timedelta
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Rental
from .services import has_overlap


class RentalRequestForm(forms.ModelForm):
    DATETIME_INPUT_FORMATS = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]

    start_at = forms.DateTimeField(
        label=_("تاریخ و ساعت تحویل"),
        input_formats=DATETIME_INPUT_FORMATS,
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition",
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )
    end_at = forms.DateTimeField(
        label=_("تاریخ و ساعت بازگرداندن"),
        input_formats=DATETIME_INPUT_FORMATS,
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition",
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )
    delivery_method = forms.ChoiceField(
        label=_("شیوه تحویل کالا"),
        widget=forms.RadioSelect(
            attrs={
                "class": "text-blue-600 focus:ring-blue-500",
            }
        ),
    )
    delivery_address = forms.CharField(
        label=_("نشانی دقیق تحویل (ویژه ارسال با پیک)"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "در صورت انتخاب ارسال با پیک، آدرس پستی دقیق خود را وارد کنید...",
                "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition",
            }
        ),
    )

    class Meta:
        model = Rental
        fields = [
            "start_at",
            "end_at",
            "delivery_method",
            "delivery_address",
        ]

    def __init__(self, *args, item=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.item = item
        self.user = user

        # Restrict delivery method options according to item preferences
        choices = []
        if self.item:
            if self.item.allow_pickup:
                choices.append((Rental.DeliveryMethod.PICKUP, _("تحویل حضوری (از محل مالک)")))
            if self.item.allow_courier:
                choices.append((Rental.DeliveryMethod.COURIER, _("ارسال با پیک (هزینه به عهده متقاضی)")))
        else:
            choices = Rental.DeliveryMethod.choices

        self.fields["delivery_method"].choices = choices
        if choices and not self.initial.get("delivery_method"):
            self.initial["delivery_method"] = choices[0][0]

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")
        delivery_method = cleaned_data.get("delivery_method")
        delivery_address = cleaned_data.get("delivery_address", "").strip()

        # 1. Check ownership
        if self.user and self.item and self.user.pk == self.item.owner_id:
            raise ValidationError(
                _("امکان ثبت درخواست اجاره برای کالای متعلق به خودتان وجود ندارد.")
            )

        # 2. Date checks
        if start_at and end_at:
            if end_at <= start_at:
                self.add_error(
                    "end_at",
                    _("زمان پایان و بازگرداندن باید پس از زمان شروع اجاره باشد."),
                )

            now_skewed = timezone.now() - timedelta(minutes=5)
            if start_at < now_skewed:
                self.add_error(
                    "start_at",
                    _("زمان تحویل کالا نمی‌تواند در گذشته باشد."),
                )

            # 3. Check overlaps
            if self.item and end_at > start_at:
                if has_overlap(self.item, start_at, end_at):
                    raise ValidationError(
                        _("این کالا در بازه زمانی انتخابی قبلاً رزرو شده است. لطفاً تاریخ دیگری انتخاب کنید.")
                    )

        # 4. Courier address requirement
        if delivery_method == Rental.DeliveryMethod.COURIER and not delivery_address:
            self.add_error(
                "delivery_address",
                _("برای شیوه ارسال با پیک، وارد کردن نشانی تحویل الزامی است."),
            )

        return cleaned_data
