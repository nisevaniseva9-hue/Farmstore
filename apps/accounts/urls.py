from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.FarmLoginView.as_view(), name="login"),
    path("logout/", views.FarmLogoutView.as_view(), name="logout"),

    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url="/account/password/change/done/",
        ),
        name="password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),

    path("profile/", views.profile, name="profile"),

    path("addresses/", views.address_list, name="address_list"),
    path("addresses/add/", views.address_create, name="address_create"),
    path("addresses/<int:pk>/edit/", views.address_edit, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
]
