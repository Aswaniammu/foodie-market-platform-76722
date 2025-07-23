from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import viewsets, status, permissions, generics
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404
from .models import Product, Cart, CartItem, Order, OrderItem, Payment
from .serializers import (
    UserSerializer, UserRegisterSerializer, ProductSerializer,
    CartSerializer, OrderSerializer
)
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
import stripe
import os

User = get_user_model()

# Stripe settings (IMPORTANT: must be set in .env)
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', None)
stripe.api_key = STRIPE_SECRET_KEY

# PUBLIC_INTERFACE
@api_view(['GET'])
def health(request):
    """Health check endpoint."""
    return Response({"message": "Server is up!"})

# PUBLIC_INTERFACE
class UserRegistrationView(generics.CreateAPIView):
    """
    User registration endpoint.
    """
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

# PUBLIC_INTERFACE
class UserLoginView(APIView):
    """
    User login endpoint supporting JWT authentication.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(request, email=email, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            })
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


# PUBLIC_INTERFACE
class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD for products.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

# PUBLIC_INTERFACE
class CartView(APIView):
    """
    Get and update user's cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current user's cart with items."""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def post(self, request):
        """
        Add/update items to cart (expects list: [{product_id, quantity}, ...])
        """
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = request.data.get('items', [])
        with transaction.atomic():
            for item in items:
                product_id = item.get('product_id')
                qty = item.get('quantity', 1)
                if not product_id or not qty:
                    continue
                product = get_object_or_404(Product, id=product_id)
                cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
                if qty > 0:
                    cart_item.quantity = qty
                    cart_item.save()
                else:
                    cart_item.delete()
        cart.refresh_from_db()
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def delete(self, request):
        """Empty the user's cart."""
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        cart.refresh_from_db()
        return Response({"detail": "Cart emptied."})


# PUBLIC_INTERFACE
class OrderViewSet(viewsets.ModelViewSet):
    """
    CRUD and history for orders (user must be authenticated; only own orders).
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Place order from cart; create Order and OrderItems."""
        cart = get_object_or_404(Cart, user=request.user)
        cart_items = cart.items.select_related('product')
        if not cart_items.exists():
            return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.create(
            user=request.user,
            total=0,
            status='pending'
        )
        total = 0
        for item in cart_items:
            price = item.product.price
            quantity = item.quantity
            OrderItem.objects.create(
                order=order,
                product=item.product,
                price=price,
                quantity=quantity,
            )
            total += price * quantity

        order.total = total
        order.save()
        cart.items.all().delete()  # Empty cart on order create

        # Optionally: return PaymentIntent client_secret (integrate with Stripe)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# PUBLIC_INTERFACE
class StripePaymentIntentView(APIView):
    """
    Generate Stripe PaymentIntent for an order.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        order_id = request.data.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=request.user)
        if order.status not in ['pending', 'failed']:
            return Response({"error": "Order not eligible for payment."}, status=400)
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(order.total * 100),  # Stripe uses cents
                currency='usd',
                metadata={'order_id': order.pk, 'email': request.user.email},
                receipt_email=request.user.email,
                automatic_payment_methods={"enabled": True},
            )
            order.stripe_payment_intent = intent['id']
            order.save()
            return Response({
                "client_secret": intent['client_secret'],
                "order_id": order.id
            })
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=500)


# PUBLIC_INTERFACE
class StripeWebhookView(APIView):
    """
    Handle Stripe webhooks (e.g., payment confirmation).
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @csrf_exempt
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', None)

        event = None
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            return Response({'error': 'Invalid payload.'}, status=400)
        except stripe.error.SignatureVerificationError:
            return Response({'error': 'Invalid signature.'}, status=400)

        # Handle successful payment event
        if event['type'] == 'payment_intent.succeeded':
            stripe_intent = event['data']['object']
            order_id = stripe_intent['metadata']['order_id']
            try:
                order = Order.objects.get(pk=order_id)
                order.status = "paid"
                order.stripe_payment_intent = stripe_intent['id']
                order.save()
                Payment.objects.create(
                    order=order,
                    stripe_payment_intent=stripe_intent['id'],
                    status='succeeded',
                    received_amount=(stripe_intent.get('amount_received') or 0) / 100
                )
            except Order.DoesNotExist:
                pass  # ignore/log
        elif event['type'] == 'payment_intent.payment_failed':
            stripe_intent = event['data']['object']
            order_id = stripe_intent['metadata'].get('order_id')
            try:
                order = Order.objects.get(pk=order_id)
                order.status = "failed"
                order.save()
            except Order.DoesNotExist:
                pass

        return Response({'status': 'ok'})

