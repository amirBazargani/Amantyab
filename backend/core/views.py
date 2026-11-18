from django.shortcuts import render

from catalog.models import Item
from core.cookies import get_last_city, get_recent_item_ids


def home(request):
    """
    Render the home page.
    Passes recently viewed items (from signed cookie) and last selected city (from cookie).
    """
    recent_ids = get_recent_item_ids(request)
    recent_items = []
    if recent_ids:
        items_dict = {
            item.pk: item
            for item in Item.objects.active()
            .filter(pk__in=recent_ids)
            .select_related("category", "owner")
            .prefetch_related("images")
        }
        # Maintain chronological order of last viewed items
        recent_items = [items_dict[pk] for pk in recent_ids if pk in items_dict]

    last_city = get_last_city(request)
    cities = (
        Item.objects.active()
        .exclude(city="")
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )

    context = {
        "recent_items": recent_items,
        "last_city": last_city,
        "cities": cities,
    }
    return render(request, "core/home.html", context)
