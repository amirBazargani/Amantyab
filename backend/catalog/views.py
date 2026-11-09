from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.notifications import notify

from .forms import ItemForm, ItemImageFormSet
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


@login_required
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
        raise PermissionDenied("شما اجازه تغییر وضعیت این کالا را ندارید.")

    item.is_active = not item.is_active
    item.save(update_fields=["is_active", "updated_at"])

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
        raise PermissionDenied("شما اجازه حذف این کالا را ندارید.")

    # Acceptance: item with rentals cannot be deleted (show message, suggest pause)
    if item.rentals.exists():
        messages.warning(
            request,
            f"کالای «{item.title}» دارای سابقه یا قرارداد اجاره است و به منظور حفظ شفافیت و سوابق امانت‌داری قابل حذف نیست. می‌توانید به جای حذف، آن را غیرفعال (متوقف) کنید تا در کاتالوگ نمایش داده نشود."
        )
        return redirect("catalog:my_items")

    if request.method == "POST":
        title = item.title
        item.delete()
        messages.success(request, f"کالای «{title}» با موفقیت حذف شد.")
        return redirect("catalog:my_items")

    context = {
        "item": item,
    }
    return render(request, "catalog/item_confirm_delete.html", context)
