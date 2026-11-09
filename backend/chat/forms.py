from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Message


class MessageForm(forms.ModelForm):
    """Form for sending a new message within an existing conversation."""

    body = forms.CharField(
        label=_("متن پیام"),
        widget=forms.Textarea(
            attrs={
                "class": "w-full rounded-2xl border border-gray-300 px-4 py-3 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition resize-none",
                "rows": 2,
                "placeholder": _("پیام خود را بنویسید..."),
            }
        ),
    )

    class Meta:
        model = Message
        fields = ["body"]

    def clean_body(self):
        body = self.cleaned_data.get("body", "").strip()
        if not body:
            raise forms.ValidationError(_("متن پیام نمی‌تواند خالی باشد."))
        return body
