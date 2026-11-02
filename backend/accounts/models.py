from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    email = models.EmailField(_("email address"), unique=True)
    phone = models.CharField(_("phone number"), max_length=20, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    neighborhood = models.CharField(_("neighborhood"), max_length=100, blank=True)
    bio = models.TextField(_("bio"), blank=True)
    is_email_verified = models.BooleanField(_("email verified"), default=False)

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.username
