from django.urls import path

from . import views

app_name = "rentals"

urlpatterns = [
    path("request/<int:item_id>/", views.rental_request, name="rental_request"),
    path("<int:pk>/pay/", views.rental_pay, name="rental_pay"),
    path("<int:pk>/receipt/", views.rental_receipt, name="rental_receipt"),
]
