from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("add/", views.product_add, name="product_add"),
    path("api/suggest-category/", views.suggest_category_api, name="suggest_category_api"),
    path("barcodes/", views.barcode_generator, name="barcode_generator"),
    path("<int:pk>/barcode/", views.product_barcode, name="product_barcode"),
    path("<int:pk>/clearance-discount/", views.apply_clearance_discount, name="apply_clearance_discount"),
    path("<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("<int:pk>/delete/", views.product_delete, name="product_delete"),
]
