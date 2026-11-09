from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import Item, ItemImage

INPUT_CLASSES = (
    "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
)
TEXTAREA_CLASSES = (
    "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm resize-y"
)
SELECT_CLASSES = (
    "w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none "
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm bg-white"
)
CHECKBOX_CLASSES = (
    "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
)


class ItemForm(forms.ModelForm):
    deposit_amount = forms.DecimalField(
        required=False,
        initial=Decimal("0"),
        label=_("مبلغ ودیعه (تومان)"),
        widget=forms.NumberInput(
            attrs={"class": INPUT_CLASSES, "placeholder": "اختیاری (پیش‌فرض ۰ تومان)", "min": "0"}
        ),
    )

    class Meta:
        model = Item
        fields = [
            "category",
            "title",
            "description",
            "brand",
            "condition",
            "hourly_price",
            "daily_price",
            "deposit_amount",
            "city",
            "neighborhood",
            "allow_pickup",
            "allow_courier",
            "address_text",
            "latitude",
            "longitude",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": SELECT_CLASSES}),
            "title": forms.TextInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "placeholder": "مثلاً: دریل چکشی رونیکس مدل ۲۷۰۱",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": TEXTAREA_CLASSES,
                    "rows": 4,
                    "placeholder": "توضیحات کامل درباره مشخصات، سلامت و نکات استفاده از کالا...",
                }
            ),
            "brand": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "مثلاً: رونیکس، بوش، ماکیتا"}
            ),
            "condition": forms.Select(attrs={"class": SELECT_CLASSES}),
            "hourly_price": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "اختیاری (تومان)", "min": "0"}
            ),
            "daily_price": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "اجباری (تومان)", "min": "1000"}
            ),
            "deposit_amount": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "مبلغ ودیعه (تومان)", "min": "0"}
            ),
            "city": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "مثلاً: تهران"}
            ),
            "neighborhood": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "مثلاً: صادقیه"}
            ),
            "allow_pickup": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "allow_courier": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "address_text": forms.TextInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "placeholder": "آدرس حدودی یا دقیق جهت تحویل حضوری کالا",
                }
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }
        labels = {
            "category": _("دسته‌بندی"),
            "title": _("عنوان کالا"),
            "description": _("توضیحات"),
            "brand": _("برند / شرکت سازنده"),
            "condition": _("وضعیت ظاهری و فنی"),
            "hourly_price": _("کرایه ساعتی (تومان)"),
            "daily_price": _("کرایه روزانه (تومان)"),
            "deposit_amount": _("مبلغ ودیعه (تومان)"),
            "city": _("شهر"),
            "neighborhood": _("محله"),
            "allow_pickup": _("امکان تحویل حضوری (پیکاپ)"),
            "allow_courier": _("امکان ارسال با پیک"),
            "address_text": _("آدرس محل تحویل"),
        }

    def clean_daily_price(self):
        daily_price = self.cleaned_data.get("daily_price")
        if daily_price is not None and daily_price <= Decimal("0"):
            raise forms.ValidationError(_("مبلغ کرایه روزانه باید بزرگتر از صفر باشد."))
        return daily_price

    def clean_deposit_amount(self):
        deposit_amount = self.cleaned_data.get("deposit_amount")
        if deposit_amount is not None and deposit_amount < Decimal("0"):
            raise forms.ValidationError(_("مبلغ ودیعه نمی‌تواند منفی باشد."))
        return deposit_amount or Decimal("0")

    def clean(self):
        cleaned_data = super().clean()
        allow_pickup = cleaned_data.get("allow_pickup")
        allow_courier = cleaned_data.get("allow_courier")

        if not allow_pickup and not allow_courier:
            raise forms.ValidationError(
                _("حداقل باید یکی از روش‌های تحویل (حضوری یا پیک) را فعال کنید.")
            )

        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")
        if (latitude is None and longitude is not None) or (
            latitude is not None and longitude is None
        ):
            raise forms.ValidationError(
                _("مختصات جغرافیایی (عرض و طول جغرافیایی) باید یا هر دو وارد شوند یا هر دو خالی باشند.")
            )

        return cleaned_data


class ItemImageForm(forms.ModelForm):
    class Meta:
        model = ItemImage
        fields = ["image", "is_primary", "order"]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "block w-full text-xs text-gray-700 file:mr-0 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100",
                    "accept": "image/*",
                }
            ),
            "is_primary": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
            "order": forms.NumberInput(
                attrs={"class": INPUT_CLASSES, "style": "width: 70px;", "min": "0"}
            ),
        }
        labels = {
            "image": _("تصویر"),
            "is_primary": _("تصویر اصلی"),
            "order": _("ترتیب"),
        }

    def has_changed(self):
        # An unpersisted extra form is considered changed only if an image file is attached
        if not self.instance.pk and not self.files.get(self.add_prefix("image")):
            return False
        return super().has_changed()


ItemImageFormSet = inlineformset_factory(
    parent_model=Item,
    model=ItemImage,
    form=ItemImageForm,
    extra=3,
    can_delete=True,
    max_num=10,
)
