from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# PUBLIC_INTERFACE
class User(AbstractUser):
    """Custom user model with email as username."""

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

# PUBLIC_INTERFACE
class Product(models.Model):
    """Represents a food item/product."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    available = models.BooleanField(default=True)
    image = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# PUBLIC_INTERFACE
class Cart(models.Model):
    """Shopping cart associated to user."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

# PUBLIC_INTERFACE
class CartItem(models.Model):
    """Product in cart."""
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

# PUBLIC_INTERFACE
class Order(models.Model):
    """Order placed by a user (confirmed from cart)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=32, default='pending')  # e.g., pending, paid, failed
    stripe_payment_intent = models.CharField(max_length=255, blank=True, null=True)  # Save PaymentIntent.id

# PUBLIC_INTERFACE
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

# PUBLIC_INTERFACE
class Payment(models.Model):
    """Payment record for orders via Stripe."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    stripe_payment_intent = models.CharField(max_length=255)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    received_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
