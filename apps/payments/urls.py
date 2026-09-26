from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/upi/download-qr/", views.download_qr, name="download_qr"),
    path("pay/upi/<str:order_number>/", views.pay_upi, name="pay_upi"),
    path("pay/upi/<str:order_number>/switch-cod/", views.switch_to_cod, name="switch_to_cod"),
]

farmer_urlpatterns = [
    path("settings/", views.payment_settings, name="payment_settings"),
    path("pending/", views.pending_verifications, name="pending_verifications"),
    path("pending/<str:order_number>/verify/", views.verify_payment, name="verify_payment"),
]
