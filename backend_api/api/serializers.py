from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Product, Cart, CartItem, Order, OrderItem, Payment

User = get_user_model()

# PUBLIC_INTERFACE
class UserSerializer(serializers.ModelSerializer):
    """Serializer for User objects."""

    class Meta:
        model = User
        fields = ('id', 'email', 'username',)


# PUBLIC_INTERFACE
class UserRegisterSerializer(serializers.ModelSerializer):
    """For user registration."""

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'username', 'password')

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    

# PUBLIC_INTERFACE
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


# PUBLIC_INTERFACE
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'product_id', 'quantity')


# PUBLIC_INTERFACE
class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ('id', 'user', 'items', 'created_at')


# PUBLIC_INTERFACE
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'price', 'quantity')


# PUBLIC_INTERFACE
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'user', 'created_at', 'total',
            'status', 'items', 'stripe_payment_intent'
        )


# PUBLIC_INTERFACE
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
