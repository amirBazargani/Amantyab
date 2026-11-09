from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("items/<int:item_pk>/start/", views.start_conversation, name="start_conversation"),
    path("<int:pk>/", views.conversation_detail, name="conversation_detail"),
]
