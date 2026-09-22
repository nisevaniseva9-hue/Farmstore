from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.current_stock, name="current_stock"),
    path("add/", views.add_stock_view, name="add_stock"),
    path("adjust/", views.adjust_stock_view, name="adjust_stock"),
    path("history/", views.inventory_history, name="history"),
    path("history/<int:product_pk>/", views.inventory_history, name="history_for_product"),
    path("notify/<int:product_pk>/", views.notify_customers, name="notify_customers"),
]
