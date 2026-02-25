from rest_framework import serializers
from django.conf import settings

from .models import (
    ProductCategory,
    Product,
    ProductMedia,
    AdditionalInformation,
    Cart,
    CartItem,
    Order,
    OrderItem,
)

def build_absolute_uri(request, path):
    """Build absolute media URL."""
    if not path:
        return None
    if request:
        return request.build_absolute_uri(f"{settings.MEDIA_URL}{path}")
    return f"{settings.MEDIA_URL}{path}"


class ProductCategorySerializer(serializers.ModelSerializer):
    """Category Serializer"""
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = ["id", "title", "slug", "image"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return build_absolute_uri(request, obj.image.name)
        return None

class ProductMediaSerializer(serializers.ModelSerializer):
    """Product Media Serializer"""
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductMedia
        fields = ["id", "image", "is_primary", "order"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            return build_absolute_uri(request, obj.image.name)
        return None

class AdditionalInfoSerializer(serializers.ModelSerializer):
    """Additional Info Serializer"""
    class Meta:
        model = AdditionalInformation
        fields = ["key", "value"]

class ProductListSerializer(serializers.ModelSerializer):
    """Product List Serializer"""
    category = serializers.StringRelatedField()
    primary_image = serializers.SerializerMethodField()
    discounted_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "price",
            "discount",
            "discounted_price",
            "is_in_stock",
            "is_featured",
            "primary_image",
            "created_at",
        ]

    def get_primary_image(self, obj):
        request = self.context.get("request")
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if image:
            return build_absolute_uri(request, image.image.name)
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Product(Details) Serializer"""
    category = ProductCategorySerializer()
    images = ProductMediaSerializer(many=True)
    additional_info = AdditionalInfoSerializer(many=True)
    discounted_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "title",
            "slug",
            "category",
            "description",
            "price",
            "discount",
            "discounted_price",
            "sku",
            "quantity",
            "is_in_stock",
            "is_featured",
            "images",
            "additional_info",
            "created_at",
            "updated_at",
        ]


class CartItemSerializer(serializers.ModelSerializer):
    """Cart Serializer"""
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        write_only=True,
        source="product",
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "subtotal"]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "items", "total_items", "total_price"]


class OrderItemSerializer(serializers.ModelSerializer):
    """Order Serializer"""
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "product_sku", "quantity", "unit_price", "subtotal"]


class OrderCreateSerializer(serializers.ModelSerializer):
    """Used for both cart checkout and buy-now."""
    class Meta:
        model = Order
        fields = ["full_name", "phone", "address", "city", "postal_code"]

    def validate(self, attrs):
        # Basic field presence validation handled by model/serializer
        return attrs


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_id",
            "status",
            "total_amount",
            "full_name",
            "phone",
            "address",
            "city",
            "postal_code",
            "is_paid",
            "paid_at",
            "transaction_id",
            "items",
            "created_at",
        ]