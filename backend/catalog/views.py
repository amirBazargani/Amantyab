from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Category, Item


def item_list(request):
    """
    Catalog browse view with filtering by search term (q), category, city, and max daily price.
    Only active items are shown to the public.
    """
    queryset = (
        Item.objects.filter(is_active=True)
        .select_related("category", "owner")
        .prefetch_related("images")
    )

    q = request.GET.get("q", "").strip()
    category_param = request.GET.get("category", "").strip()
    city = request.GET.get("city", "").strip()
    max_price_param = request.GET.get("max_price", "").strip()

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(brand__icontains=q)
        )

    if category_param:
        if category_param.isdigit():
            queryset = queryset.filter(category_id=int(category_param))
        else:
            queryset = queryset.filter(category__slug=category_param)

    if city:
        queryset = queryset.filter(city__icontains=city)

    if max_price_param:
        try:
            max_price = Decimal(max_price_param)
            if max_price > 0:
                queryset = queryset.filter(daily_price__lte=max_price)
        except (InvalidOperation, ValueError):
            pass

    categories = Category.objects.all().order_by("name")
    cities = (
        Item.objects.filter(is_active=True)
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )

    context = {
        "items": queryset,
        "categories": categories,
        "cities": cities,
        "q": q,
        "selected_category": category_param,
        "selected_city": city,
        "max_price": max_price_param,
        "total_count": queryset.count(),
    }
    return render(request, "catalog/item_list.html", context)


def item_detail(request, pk):
    """
    Detail page for a specific item.
    Shows images, prices, deposit amount, owner information, and delivery options.
    Inactive items are only viewable by their owner or staff; otherwise 404.
    """
    item = get_object_or_404(
        Item.objects.select_related("owner", "category").prefetch_related("images"),
        pk=pk,
    )

    is_owner_or_staff = request.user.is_authenticated and (
        request.user == item.owner or request.user.is_staff
    )
    if not item.is_active and not is_owner_or_staff:
        raise Http404("این کالا در حال حاضر غیرفعال است.")

    images = list(item.images.all())
    primary_image = next((img for img in images if img.is_primary), None)
    if not primary_image and images:
        primary_image = images[0]

    context = {
        "item": item,
        "images": images,
        "primary_image": primary_image,
        "is_owner": request.user.is_authenticated and request.user == item.owner,
        "can_manage": is_owner_or_staff,
    }
    return render(request, "catalog/item_detail.html", context)
