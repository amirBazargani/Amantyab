from datetime import timedelta
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Dispute, Rental
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
    delivery_latitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "id_delivery_latitude"}),
    )
    delivery_longitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "id_delivery_longitude"}),
    )

    class Meta:
        model = Rental
        fields = [
            "start_at",
            "end_at",
            "delivery_method",
            "delivery_address",
            "delivery_latitude",
            "delivery_longitude",
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
        delivery_latitude = cleaned_data.get("delivery_latitude")
        delivery_longitude = cleaned_data.get("delivery_longitude")

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

        # 4. Courier address and coordinates
        if delivery_method == Rental.DeliveryMethod.COURIER:
            if not delivery_address:
                self.add_error(
                    "delivery_address",
                    _("برای شیوه ارسال با پیک، وارد کردن نشانی تحویل الزامی است."),
                )
        else:
            # In pickup mode, delivery coordinates and address do not apply
            cleaned_data["delivery_latitude"] = None
            cleaned_data["delivery_longitude"] = None
            delivery_latitude = None
            delivery_longitude = None

        # 5. Geographic validation (both-or-neither and ranges)
        if (delivery_latitude is None and delivery_longitude is not None) or (
            delivery_latitude is not None and delivery_longitude is None
        ):
            raise ValidationError(
                _("مختصات جغرافیایی تحویل باید هر دو مشخص شوند یا هر دو خالی باشند.")
            )

        if delivery_latitude is not None:
            if delivery_latitude < Decimal("-90") or delivery_latitude > Decimal("90"):
                self.add_error(
                    "delivery_latitude",
                    _("عرض جغرافیایی باید بین ۹۰- تا ۹۰ درجه باشد."),
                )

        if delivery_longitude is not None:
            if delivery_longitude < Decimal("-180") or delivery_longitude > Decimal("180"):
                self.add_error(
                    "delivery_longitude",
                    _("طول جغرافیایی باید بین ۱۸۰- تا ۱۸۰ درجه باشد."),
                )

        return cleaned_data


class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ["reason"]
        widgets = {
            "reason": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": _("علت بروز اختلاف، خسارت وارده، عدم تحویل یا مغایرت را به طور کامل تشریح فرمایید..."),
                    "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition",
                }
            ),
        }
        labels = {
            "reason": _("شرح علت اختلاف"),
        }

    def clean_reason(self):
        reason = self.cleaned_data.get("reason", "").strip()
        if not reason:
            raise ValidationError(_("لطفاً علت بروز اختلاف را وارد نمایید."))
        if len(reason) < 10:
            raise ValidationError(_("شرح علت اختلاف باید حداقل شامل ۱۰ کاراکتر باشد."))
        return reason


class DisputeResolveForm(forms.ModelForm):
    deposit_decision = forms.ChoiceField(
        label=_("تصمیم‌گیری در مورد ودیعه"),
        choices=Dispute.DepositDecision.choices,
        widget=forms.RadioSelect(
            attrs={
                "class": "text-blue-600 focus:ring-blue-500",
            }
        ),
    )

    class Meta:
        model = Dispute
        fields = ["deposit_decision", "resolution_note"]
        widgets = {
            "resolution_note": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": _("توضیحات و مستندات رأی داوری برای اطلاع طرفین..."),
                    "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition",
                }
            ),
        }
        labels = {
            "resolution_note": _("یادداشت و نتیجه‌گیری مدیر"),
        }

    def clean_deposit_decision(self):
        decision = self.cleaned_data.get("deposit_decision")
        if decision not in Dispute.DepositDecision.values:
            raise ValidationError(_("لطفاً یک تصمیم معتبر برای ودیعه انتخاب کنید."))
        return decision

