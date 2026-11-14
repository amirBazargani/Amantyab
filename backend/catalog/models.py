from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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


class ItemQuerySet(models.QuerySet):
    def active(self):
        """Return only active items available to the public."""
        return self.filter(is_active=True)

    def in_city(self, city):
        """Filter items by city name (case-insensitive substring)."""
        if not city or not str(city).strip():
            return self
        return self.filter(city__icontains=str(city).strip())

    def in_category(self, category):
        """
        Filter items by category instance, primary key, or slug.
        Includes all descendant child categories when applicable.
        """
        if not category:
            return self

        if isinstance(category, Category):
            cat_ids = [category.pk] + list(category.children.values_list("pk", flat=True))
            return self.filter(category_id__in=cat_ids)

        cat_str = str(category).strip()
        if not cat_str:
            return self

        if isinstance(category, int) or cat_str.isdigit():
            cat_id = int(cat_str)
            cat = Category.objects.filter(pk=cat_id).prefetch_related("children").first()
            if cat:
                cat_ids = [cat.pk] + list(cat.children.values_list("pk", flat=True))
                return self.filter(category_id__in=cat_ids)
            return self.filter(category_id=cat_id)

        cat = Category.objects.filter(slug=cat_str).prefetch_related("children").first()
        if cat:
            cat_ids = [cat.pk] + list(cat.children.values_list("pk", flat=True))
            return self.filter(category_id__in=cat_ids)
        return self.filter(category__slug=cat_str)

    def search(self, q):
        """Search items by title, description, or brand."""
        if not q or not str(q).strip():
            return self
        query = str(q).strip()
        return self.filter(
            models.Q(title__icontains=query)
            | models.Q(description__icontains=query)
            | models.Q(brand__icontains=query)
        )

    def price_up_to(self, max_price):
        """Filter items with daily price less than or equal to max_price."""
        if max_price is None or str(max_price).strip() == "":
            return self
        try:
            val = Decimal(str(max_price))
            if val > 0:
                return self.filter(daily_price__lte=val)
        except (InvalidOperation, ValueError, TypeError):
            pass
        return self

    def available_between(self, start, end):
        """
        Return items that have no overlapping blocking (non-cancelled) rentals
        between start and end.
        """
        if not start or not end:
            return self
        Rental = apps.get_model("rentals", "Rental")
        busy_item_ids = (
            Rental.objects.blocking()
            .overlapping(start=start, end=end)
            .values_list("item_id", flat=True)
        )
        return self.exclude(pk__in=busy_item_ids)


class Item(models.Model):
    objects = ItemQuerySet.as_manager()

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
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-90.0")),
            MaxValueValidator(Decimal("90.0")),
        ],
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("-180.0")),
            MaxValueValidator(Decimal("180.0")),
        ],
    )
    address_text = models.CharField(_("address text"), max_length=255, blank=True)
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
            models.CheckConstraint(
                condition=(
                    (models.Q(latitude__isnull=True) & models.Q(longitude__isnull=True))
                    | (models.Q(latitude__isnull=False) & models.Q(longitude__isnull=False))
                ),
                name="item_lat_lng_both_or_neither",
            ),
        ]
        indexes = [
            models.Index(fields=["city", "is_active"], name="item_city_active_idx"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if (self.latitude is None and self.longitude is not None) or (
            self.latitude is not None and self.longitude is None
        ):
            raise ValidationError(
                _("Latitude and longitude must either both be set or both be empty.")
            )


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
