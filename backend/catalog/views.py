import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.cookies import add_recent_item_id, set_last_city
from core.decorators import verified_required
from core.notifications import notify
from reviews.models import Review

from .forms import ItemForm, ItemImageFormSet
from .models import Category, Item

logger = logging.getLogger("amanatyab.catalog")


def item_list(request):
    """
    Catalog browse view with filtering by search term (q), category, city, and max daily price.
    Only active items are shown to the public. Uses chained ItemQuerySet methods.
    Stores and persists active search filters in request.session across page visits.
    """
    filter_keys = ("q", "category", "city", "max_price")
    is_clearing = "clear" in request.GET

    if is_clearing:
        request.session.pop("catalog_search_filters", None)
        q = ""
        category_param = ""
        city = ""
        max_price_param = ""
    elif any(key in request.GET for key in filter_keys):
        q = request.GET.get("q", "").strip()
        category_param = request.GET.get("category", "").strip()
        city = request.GET.get("city", "").strip()
        max_price_param = request.GET.get("max_price", "").strip()

        if any([q, category_param, city, max_price_param]):
            request.session["catalog_search_filters"] = {
                "q": q,
                "category": category_param,
                "city": city,
                "max_price": max_price_param,
            }
        else:
            request.session.pop("catalog_search_filters", None)
    else:
        saved_filters = request.session.get("catalog_search_filters") or {}
        q = saved_filters.get("q", "").strip()
        category_param = saved_filters.get("category", "").strip()
        city = saved_filters.get("city", "").strip()
        max_price_param = saved_filters.get("max_price", "").strip()

    queryset = (
        Item.objects.active()
        .search(q)
        .in_category(category_param)
        .in_city(city)
        .price_up_to(max_price_param)
        .select_related("category", "owner")
        .prefetch_related("images")
    )

    items = list(queryset)
    categories = Category.objects.all().order_by("name")
    cities = (
        Item.objects.active()
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )

    context = {
        "items": items,
        "categories": categories,
        "cities": cities,
        "q": q,
        "selected_category": category_param,
        "selected_city": city,
        "max_price": max_price_param,
        "total_count": len(items),
    }
    response = render(request, "catalog/item_list.html", context)
    if city:
        set_last_city(response, city)
    return response


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

    # Calculate reviews left for this item (by renters reviewing the owner)
    reviews = (
        Review.objects.filter(rental__item=item, reviewee_role=Review.Role.OWNER)
        .select_related("reviewer")
        .order_by("-created_at")
    )
    avg_rating = reviews.average_rating()
    review_count = reviews.count()

    context = {
        "item": item,
        "images": images,
        "primary_image": primary_image,
        "reviews": reviews,
        "avg_rating": round(avg_rating, 1) if avg_rating else None,
        "review_count": review_count,
        "is_owner": request.user.is_authenticated and request.user == item.owner,
        "can_manage": is_owner_or_staff,
    }
    response = render(request, "catalog/item_detail.html", context)
    add_recent_item_id(response, request, item.pk)
    if item.city:
        set_last_city(response, item.city)
    return response


@login_required
def my_items(request):
    """
    Owner's dashboard view for their own items.
    Shows both active and inactive items, image thumbnails,
    and real-time status of current/ongoing rentals (who rented it and time remaining).
    """
    items_qs = (
        Item.objects.filter(owner=request.user)
        .select_related("category")
        .prefetch_related("images", "rentals__renter")
        .order_by("-created_at")
    )

    items = list(items_qs)
    now = timezone.now()

    for item in items:
        item_rentals = list(item.rentals.all())
        item.total_rentals_count = len(item_rentals)
        item.has_rentals = len(item_rentals) > 0

        # Find current active/ongoing rental
        # Active statuses: confirmed, handed_over, disputed
        ongoing = [
            r for r in item_rentals
            if r.status in ["confirmed", "handed_over", "disputed"]
        ]

        active_rental = None
        if ongoing:
            ongoing.sort(key=lambda r: r.end_at)
            for r in ongoing:
                if r.end_at >= now or r.status == "handed_over":
                    active_rental = r
                    break
            if not active_rental:
                active_rental = ongoing[-1]

        item.active_rental = active_rental

    context = {
        "items": items,
        "total_count": len(items),
        "active_count": sum(1 for i in items if i.is_active),
        "inactive_count": sum(1 for i in items if not i.is_active),
        "now": now,
    }
    return render(request, "catalog/my_items.html", context)


@verified_required
def item_create(request):
    """
    Register a new item with image uploads.
    """
    if request.method == "POST":
        form = ItemForm(request.POST)
        formset = ItemImageFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()

            formset.instance = item
            formset.save()

            # Ensure at least one image is marked primary if any exist
            images = list(item.images.all())
            if images and not any(img.is_primary for img in images):
                images[0].is_primary = True
                images[0].save(update_fields=["is_primary"])

            # Notify owner upon registration of a new item (email + SMS)
            notify(request.user, "item_registered", {"title": item.title}, item=item)

            logger.info(
                "Item created: item_id=%s title=%s owner_id=%s",
                item.pk,
                item.title,
                request.user.pk,
            )

            messages.success(request, f"کالای «{item.title}» با موفقیت ثبت شد.")
            return redirect("catalog:item_detail", pk=item.pk)
    else:
        form = ItemForm()
        formset = ItemImageFormSet()

    context = {
        "form": form,
        "formset": formset,
        "title": "ثبت کالای جدید برای امانت",
        "is_create": True,
    }
    return render(request, "catalog/item_form.html", context)


@login_required
def item_edit(request, pk):
    """
    Edit an existing item and its images.
    Restricted strictly to the item's owner (others get 403 Forbidden).
    """
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        logger.warning(
            "Permission denied on item edit: item_id=%s user_id=%s owner_id=%s",
            item.pk,
            request.user.pk,
            item.owner_id,
        )
        raise PermissionDenied("شما اجازه ویرایش این کالا را ندارید.")

    if request.method == "POST":
        form = ItemForm(request.POST, instance=item)
        formset = ItemImageFormSet(request.POST, request.FILES, instance=item)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            # Ensure at least one image is marked primary if any exist
            images = list(item.images.all())
            if images and not any(img.is_primary for img in images):
                images[0].is_primary = True
                images[0].save(update_fields=["is_primary"])

            logger.info(
                "Item edited: item_id=%s title=%s user_id=%s",
                item.pk,
                item.title,
                request.user.pk,
            )
            messages.success(request, f"تغییرات کالای «{item.title}» با موفقیت ذخیره شد.")
            return redirect("catalog:item_detail", pk=item.pk)
    else:
        form = ItemForm(instance=item)
        formset = ItemImageFormSet(instance=item)

    context = {
        "form": form,
        "formset": formset,
        "item": item,
        "title": f"ویرایش «{item.title}»",
        "is_create": False,
    }
    return render(request, "catalog/item_form.html", context)


@login_required
@require_POST
def item_toggle_active(request, pk):
    """
    Quickly toggle the active/inactive status of an item.
    Restricted strictly to the item's owner (others get 403 Forbidden).
    """
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        logger.warning(
            "Permission denied on item toggle: item_id=%s user_id=%s owner_id=%s",
            item.pk,
            request.user.pk,
            item.owner_id,
        )
        raise PermissionDenied("شما اجازه تغییر وضعیت این کالا را ندارید.")

    item.is_active = not item.is_active
    item.save(update_fields=["is_active", "updated_at"])

    logger.info(
        "Item active status toggled: item_id=%s is_active=%s user_id=%s",
        item.pk,
        item.is_active,
        request.user.pk,
    )

    status_label = (
        "فعال شد و در کاتالوگ عمومی نمایش داده می‌شود"
        if item.is_active
        else "غیرفعال شد و از کاتالوگ عمومی مخفی گردید"
    )
    messages.success(request, f"کالای «{item.title}» {status_label}.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("catalog:my_items")


@login_required
def item_delete(request, pk):
    """
    Delete an item if it has no associated rentals.
    Restricted strictly to the item's owner (others get 403 Forbidden).
    If any rentals exist, deletion is rejected with an informative message.
    """
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        logger.warning(
            "Permission denied on item delete: item_id=%s user_id=%s owner_id=%s",
            item.pk,
            request.user.pk,
            item.owner_id,
        )
        raise PermissionDenied("شما اجازه حذف این کالا را ندارید.")

    # Acceptance: item with rentals cannot be deleted (show message, suggest pause)
    if item.rentals.exists():
        logger.warning(
            "Item deletion blocked due to existing rentals: item_id=%s user_id=%s",
            item.pk,
            request.user.pk,
        )
        messages.warning(
            request,
            f"کالای «{item.title}» دارای سابقه یا قرارداد اجاره است و به منظور حفظ شفافیت و سوابق امانت‌داری قابل حذف نیست. می‌توانید به جای حذف، آن را غیرفعال (متوقف) کنید تا در کاتالوگ نمایش داده نشود."
        )
        return redirect("catalog:my_items")

    if request.method == "POST":
        title = item.title
        item_pk = item.pk
        item.delete()
        logger.info(
            "Item deleted: item_id=%s title=%s user_id=%s",
            item_pk,
            title,
            request.user.pk,
        )
        messages.success(request, f"کالای «{title}» با موفقیت حذف شد.")
        return redirect("catalog:my_items")

    context = {
        "item": item,
    }
    return render(request, "catalog/item_confirm_delete.html", context)
