from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("enquiry/", views.enquiry, name="enquiry"),
    path("<str:slug>/", views.page, name="page"),
]
