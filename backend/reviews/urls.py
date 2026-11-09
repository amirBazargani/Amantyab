from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("rentals/<int:rental_pk>/new/", views.review_create, name="review_create"),
]
