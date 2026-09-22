from django.urls import path

from . import farmer_views

app_name = "farmer_orders"

urlpatterns = [
    path("", farmer_views.dashboard, name="dashboard"),
    path("orders/", farmer_views.order_list, name="order_list"),
    path("orders/<str:order_number>/", farmer_views.order_detail, name="order_detail"),
    path("customers/", farmer_views.customer_list, name="customer_list"),
]
