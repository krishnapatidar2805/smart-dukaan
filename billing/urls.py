from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    path("new/", views.bill_create, name="bill_create"),
    path("", views.bill_list, name="bill_list"),
    path("<int:pk>/", views.bill_detail, name="bill_detail"),
    path("<int:pk>/pdf/", views.bill_pdf, name="bill_pdf"),
    path("<int:pk>/thermal/", views.bill_thermal, name="bill_thermal"),
    path("<int:pk>/return/", views.bill_return_create, name="bill_return_create"),
    path("returns/", views.bill_return_list, name="bill_return_list"),
    path("cash-register/", views.cash_register_view, name="cash_register"),
    path("cash-register/history/", views.cash_register_history, name="cash_register_history"),
    path("api/customer-lookup/", views.customer_lookup_api, name="customer_lookup_api"),
    path("api/product/<int:pk>/", views.product_price_api, name="product_price_api"),
]
