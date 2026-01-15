from django.urls import path
from . import views


urlpatterns = [
    path('qr-payments/webhook/', views.QRPaymentWebhookView.as_view(), name='qr-payment_webhook'),
]
