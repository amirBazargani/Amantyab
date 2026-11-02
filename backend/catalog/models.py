from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=120, unique=True, allow_unicode=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("parent category"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    class Condition(models.TextChoices):
        NEW = "new", _("New")
        LIKE_NEW = "like_new", _("Like new")
        GOOD = "good", _("Good")
        FAIR = "fair", _("Fair")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("owner"),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name=_("category"),
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"))
    brand = models.CharField(_("brand"), max_length=100, blank=True)
    condition = models.CharField(
        _("condition"),
        max_length=20,
        choices=Condition.choices,
    )
    hourly_price = models.DecimalField(
        _("hourly price"),
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
    )
    daily_price = models.DecimalField(
        _("daily price"),
        max_digits=12,
        decimal_places=0,
    )
    deposit_amount = models.DecimalField(
        _("deposit amount"),
        max_digits=12,
        decimal_places=0,
        default=0,
    )
    city = models.CharField(_("city"), max_length=100)
    neighborhood = models.CharField(_("neighborhood"), max_length=100)
    allow_pickup = models.BooleanField(_("allow pickup"), default=True)
    allow_courier = models.BooleanField(_("allow courier"), default=False)
    is_active = models.BooleanField(_("is active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("item")
        verbose_name_plural = _("items")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(daily_price__gt=0),
                name="item_daily_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(allow_pickup=True) | models.Q(allow_courier=True),
                name="item_at_least_one_delivery_method",
            ),
        ]
        indexes = [
            models.Index(fields=["city", "is_active"], name="item_city_active_idx"),
        ]

    def __str__(self):
        return self.title


class ItemImage(models.Model):
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name=_("item"),
    )
    image = models.ImageField(_("image"), upload_to="items/%Y/%m/")
    is_primary = models.BooleanField(_("is primary"), default=False)
    order = models.PositiveIntegerField(_("order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("item image")
        verbose_name_plural = _("item images")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.item.title} image ({self.id})"
