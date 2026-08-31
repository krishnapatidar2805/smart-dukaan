from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("assistant/", views.ai_chat, name="ai_chat"),
    path("assistant/ask/", views.ai_ask_api, name="ai_ask_api"),
    path("store/<int:shop_id>/", views.public_storefront, name="public_storefront"),
    path("store/<int:shop_id>/qr/", views.store_qr_standee, name="store_qr_standee"),
    path("export/sales/", views.export_sales_csv, name="export_sales_csv"),
    path("export/inventory/", views.export_inventory_csv, name="export_inventory_csv"),
    path("export/customers/", views.export_customers_csv, name="export_customers_csv"),
]
