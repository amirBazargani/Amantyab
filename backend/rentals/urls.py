from django.urls import path

from . import views

app_name = "rentals"

urlpatterns = [
    path("request/<int:item_id>/", views.rental_request, name="rental_request"),
    path("my-rentals/", views.my_rentals, name="my_rentals"),
    path("owner-rentals/", views.owner_rentals, name="owner_rentals"),
    path("<int:pk>/pay/", views.rental_pay, name="rental_pay"),
    path("<int:pk>/receipt/", views.rental_receipt, name="rental_receipt"),
    path("<int:pk>/", views.rental_detail, name="rental_detail"),
    path("<int:pk>/handover/", views.handover, name="handover"),
    path("<int:pk>/return/", views.mark_returned, name="mark_returned"),
    path("<int:pk>/confirm-return/", views.confirm_return, name="confirm_return"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/dispute/", views.dispute_open, name="dispute_open"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("disputes/", views.admin_dispute_list, name="admin_dispute_list"),
    path("disputes/<int:pk>/resolve/", views.admin_dispute_resolve, name="admin_dispute_resolve"),
]
