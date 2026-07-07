from django.urls import path

from . import views

app_name = "examinations"

urlpatterns = [
    path("", views.exams, name="exams"),
    path("results/", views.results, name="results"),
    path("predictions/", views.predictions, name="predictions"),
]
