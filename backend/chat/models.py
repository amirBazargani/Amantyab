from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name=_("item"),
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name=_("renter"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("conversation")
        verbose_name_plural = _("conversations")
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "renter"],
                name="unique_item_renter_conversation",
            ),
        ]

    @property
    def owner(self):
        return self.item.owner

    def __str__(self):
        item_title = getattr(self.item, "title", self.item_id)
        return f"Conversation: {self.renter} & {self.owner} ({item_title})"

    def clean(self):
        super().clean()
        if self.item_id and self.renter_id:
            if self.renter_id == self.item.owner_id:
                raise ValidationError(
                    {"renter": _("Item owner cannot start a conversation with themselves.")}
                )


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("conversation"),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name=_("sender"),
    )
    body = models.TextField(_("body"))
    is_read = models.BooleanField(_("is read"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ["created_at"]

    def __str__(self):
        return f"Message #{self.pk or 'new'} from {self.sender} in Conversation #{self.conversation_id}"

    def clean(self):
        super().clean()
        if self.conversation_id and self.sender_id:
            conversation = self.conversation
            item_owner_id = conversation.item.owner_id
            renter_id = conversation.renter_id
            if self.sender_id not in (item_owner_id, renter_id):
                raise ValidationError(
                    {"sender": _("Message sender must be either the item owner or the renter.")}
                )
