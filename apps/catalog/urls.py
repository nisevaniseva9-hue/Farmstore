from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    # Public
    path("products/", views.product_list, name="product_list"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("category/", views.category_list, name="category_list"),
    path("category/<slug:slug>/", views.category_detail, name="category_detail"),
]

farmer_urlpatterns = [
    path("products/", views.farmer_product_list, name="farmer_product_list"),
    path("products/add/", views.farmer_product_add, name="farmer_product_add"),
    path("products/<int:pk>/edit/", views.farmer_product_edit, name="farmer_product_edit"),
    path(
        "products/<int:pk>/images/add/",
        views.farmer_product_image_add, name="farmer_product_image_add",
    ),
    path(
        "products/<int:pk>/images/<int:image_pk>/delete/",
        views.farmer_product_image_delete, name="farmer_product_image_delete",
    ),
    path("categories/", views.farmer_category_list, name="farmer_category_list"),
    path("categories/add/", views.farmer_category_add, name="farmer_category_add"),
    path("categories/<int:pk>/edit/", views.farmer_category_edit, name="farmer_category_edit"),
]
