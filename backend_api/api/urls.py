from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    health,
    UserRegistrationView,
    UserLoginView,
    ProductViewSet,
    CartView,
    OrderViewSet,
    StripePaymentIntentView,
    StripeWebhookView
)

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('health/', health, name='Health'),
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', UserLoginView.as_view(), name='user-login'),
    path('cart/', CartView.as_view(), name='cart'),
    path('payments/intent/', StripePaymentIntentView.as_view(), name='stripe-payment-intent'),
    path('payments/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
] + router.urls
