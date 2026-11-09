from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Review

RATING_CHOICES = [
    (5, _("۵ ستاره (عالی)")),
    (4, _("۴ ستاره (خیلی خوب)")),
    (3, _("۳ ستاره (متوسط)")),
    (2, _("۲ ستاره (ضعیف)")),
    (1, _("۱ ستاره (خیلی بد)")),
]


class ReviewForm(forms.ModelForm):
    """Form for submitting a rating and review for a rental."""

    rating = forms.TypedChoiceField(
        choices=RATING_CHOICES,
        coerce=int,
        label=_("امتیاز شما"),
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition bg-white",
            }
        ),
    )
    comment = forms.CharField(
        label=_("نظر و تجربه شما (اختیاری)"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full rounded-xl border border-gray-300 px-3.5 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition resize-y",
                "rows": 4,
                "placeholder": _("تجربه خود را از همکاری و نحوه امانت‌داری بنویسید..."),
            }
        ),
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if not rating or not (1 <= rating <= 5):
            raise forms.ValidationError(_("امتیاز باید بین ۱ تا ۵ باشد."))
        return rating
