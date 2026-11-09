from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.item_list, name="item_list"),
    path("my-items/", views.my_items, name="my_items"),
    path("new/", views.item_create, name="item_create"),
    path("<int:pk>/", views.item_detail, name="item_detail"),
    path("<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("<int:pk>/toggle-active/", views.item_toggle_active, name="item_toggle_active"),
    path("<int:pk>/delete/", views.item_delete, name="item_delete"),
]
