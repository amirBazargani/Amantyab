from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from catalog.models import Item
from .forms import MessageForm
from .models import Conversation, Message


@login_required
def inbox(request):
    """
    Inbox view showing all conversations the logged-in user participates in
    either as renter or as item owner.
    """
    conversations = (
        Conversation.objects.filter(
            Q(renter=request.user) | Q(item__owner=request.user)
        )
        .select_related("item", "renter", "item__owner")
        .prefetch_related("messages", "item__images")
        .order_by("-updated_at")
    )

    conversations_data = []
    for conv in conversations:
        counterpart = conv.item.owner if conv.renter_id == request.user.pk else conv.renter
        messages_qs = list(conv.messages.all())
        last_message = messages_qs[-1] if messages_qs else None
        unread_count = sum(
            1 for m in messages_qs if not m.is_read and m.sender_id != request.user.pk
        )
        primary_img = next((img for img in conv.item.images.all() if img.is_primary), None)
        if not primary_img and conv.item.images.all():
            primary_img = conv.item.images.all()[0]

        conversations_data.append(
            {
                "conversation": conv,
                "counterpart": counterpart,
                "last_message": last_message,
                "unread_count": unread_count,
                "primary_image": primary_img,
            }
        )

    context = {
        "conversations_data": conversations_data,
    }
    return render(request, "chat/inbox.html", context)


@login_required
def start_conversation(request, item_pk):
    """
    Starts or opens an existing conversation between a renter and item owner.
    The item owner cannot start a conversation with themselves.
    """
    item = get_object_or_404(Item.objects.select_related("owner"), pk=item_pk)

    if request.user == item.owner:
        messages.error(request, _("شما نمی‌توانید با خودتان درباره کالای خودتان گفتگو کنید."))
        return redirect("catalog:item_detail", pk=item.pk)

    conversation, _created = Conversation.objects.get_or_create(
        item=item,
        renter=request.user,
    )
    return redirect("chat:conversation_detail", pk=conversation.pk)


@login_required
def conversation_detail(request, pk):
    """
    Displays the conversation thread with messages in chronological order.
    Only the 2 participants (or staff) can access.
    Incoming messages are automatically marked as read.
    """
    conversation = get_object_or_404(
        Conversation.objects.select_related("item", "item__owner", "renter"),
        pk=pk,
    )

    is_renter = request.user.pk == conversation.renter_id
    is_owner = request.user.pk == conversation.item.owner_id

    if not is_renter and not is_owner and not request.user.is_staff:
        raise PermissionDenied(_("شما اجازه دسترسی به این گفتگو را ندارید."))

    # Mark incoming unread messages as read
    conversation.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.full_clean()
            msg.save()
            # Update updated_at of conversation
            conversation.save(update_fields=["updated_at"])
            return redirect("chat:conversation_detail", pk=conversation.pk)
    else:
        form = MessageForm()

    messages_list = conversation.messages.select_related("sender").order_by("created_at")
    counterpart = conversation.item.owner if is_renter else conversation.renter

    context = {
        "conversation": conversation,
        "item": conversation.item,
        "counterpart": counterpart,
        "messages_list": messages_list,
        "form": form,
        "is_owner": is_owner,
        "is_renter": is_renter,
    }
    return render(request, "chat/conversation_detail.html", context)
