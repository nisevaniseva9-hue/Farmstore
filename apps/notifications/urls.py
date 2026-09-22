from django.urls import path

from . import views

app_name = "farmer_notifications"

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("test/", views.notification_test, name="notification_test"),
]
