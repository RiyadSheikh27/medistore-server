import logging
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from utils.views import APIResponse
from .models import Product, ProductCategory, Cart, CartItem, Order, OrderItem
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCategorySerializer,
    CartSerializer,
    CartItemSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
)

logger = logging.getLogger(__name__)


# ─── Pagination ───────────────────────────────────────────────────────────────

class ProductPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


# ─── Category ─────────────────────────────────────────────────────────────────

class ProductCategoryListAPIView(APIResponse, APIView):
    """
    GET /api/products/categories/
    List all active product categories with product count.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            categories = (
                ProductCategory.objects.filter(is_active=True)
                .annotate(product_count=Count("products", filter=Q(products__is_active=True)))
                .order_by("title")
            )
            serializer = ProductCategorySerializer(categories, many=True, context={"request": request})
            return self.success_response(
                message="Categories retrieved successfully.",
                data=serializer.data,
            )
        except Exception as e:
            logger.exception("Error fetching categories")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── Product List ─────────────────────────────────────────────────────────────

class ProductListAPIView(APIResponse, APIView):
    """
    GET /api/products/
    Query Params:
        - search       : search by name / title / description
        - category     : filter by category slug
        - featured     : true/false
        - in_stock     : true/false
        - min_price    : decimal
        - max_price    : decimal
        - ordering     : price / -price / created_at / -created_at
        - page, page_size
    """
    permission_classes = [permissions.AllowAny]
    pagination_class = ProductPagination

    def get(self, request):
        try:
            queryset = (
                Product.objects.select_related("category")
                .prefetch_related("images")
                .filter(is_active=True)
            )

            # Search
            search = request.query_params.get("search")
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search)
                    | Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

            # Category filter
            category_slug = request.query_params.get("category")
            if category_slug:
                queryset = queryset.filter(category__slug=category_slug)

            # Featured filter
            featured = request.query_params.get("featured")
            if featured and featured.lower() == "true":
                queryset = queryset.filter(is_featured=True)

            # Stock filter
            in_stock = request.query_params.get("in_stock")
            if in_stock and in_stock.lower() == "true":
                queryset = queryset.filter(quantity__gt=0)

            # Price range
            min_price = request.query_params.get("min_price")
            max_price = request.query_params.get("max_price")
            if min_price:
                queryset = queryset.filter(price__gte=min_price)
            if max_price:
                queryset = queryset.filter(price__lte=max_price)

            # Ordering
            ordering = request.query_params.get("ordering", "-created_at")
            allowed_ordering = ["price", "-price", "created_at", "-created_at", "name", "-name"]
            if ordering in allowed_ordering:
                queryset = queryset.order_by(ordering)

            # Paginate
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            serializer = ProductListSerializer(page, many=True, context={"request": request})

            return self.success_response(
                message="Products retrieved successfully.",
                data=serializer.data,
                meta={
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                },
            )

        except ValidationError as e:
            return self.error_response(
                message="Validation error.",
                errors=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error fetching product list")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── Product Detail ───────────────────────────────────────────────────────────

class ProductDetailAPIView(APIResponse, APIView):
    """
    GET /api/products/<slug>/
    Retrieve full product details by slug.
    Also exposes:
        GET /api/products/<slug>/related/   → related products (same category)
    """
    permission_classes = [permissions.AllowAny]

    def _get_product(self, slug):
        return (
            Product.objects.select_related("category")
            .prefetch_related("images", "additional_info")
            .filter(is_active=True)
            .get(slug=slug)
        )

    def get(self, request, slug):
        try:
            product = self._get_product(slug)
            serializer = ProductDetailSerializer(product, context={"request": request})
            return self.success_response(
                message="Product retrieved successfully.",
                data=serializer.data,
            )
        except Product.DoesNotExist:
            return self.error_response(
                message="Product not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception("Error fetching product detail")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProductRelatedAPIView(APIResponse, APIView):
    """
    GET /api/products/<slug>/related/
    Returns up to 8 related products from the same category.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        try:
            product = Product.objects.get(slug=slug, is_active=True)
            related = (
                Product.objects.filter(category=product.category, is_active=True)
                .exclude(id=product.id)
                .prefetch_related("images")
                .order_by("-is_featured", "-created_at")[:8]
            )
            serializer = ProductListSerializer(related, many=True, context={"request": request})
            return self.success_response(
                message="Related products retrieved successfully.",
                data=serializer.data,
            )
        except Product.DoesNotExist:
            return self.error_response(
                message="Product not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception("Error fetching related products")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LatestProductsAPIView(APIResponse, APIView):
    """
    GET /api/products/latest/
    Returns the 10 most recently added active products.
    Custom endpoint defined inside the Product domain.
    """
    permission_classes = [permissions.AllowAny]
    LIMIT = 10

    def get(self, request):
        try:
            products = (
                Product.objects.select_related("category")
                .prefetch_related("images")
                .filter(is_active=True)
                .order_by("-created_at")[: self.LIMIT]
            )
            serializer = ProductListSerializer(products, many=True, context={"request": request})
            return self.success_response(
                message=f"Latest {self.LIMIT} products retrieved successfully.",
                data=serializer.data,
            )
        except Exception as e:
            logger.exception("Error fetching latest products")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── Cart ─────────────────────────────────────────────────────────────────────

class CartAPIView(APIResponse, APIView):
    """
    GET    /api/cart/          → View cart
    POST   /api/cart/          → Add item  { product_id, quantity }
    DELETE /api/cart/          → Clear entire cart
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_or_create_cart(self, user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    def get(self, request):
        try:
            cart = self._get_or_create_cart(request.user)
            serializer = CartSerializer(cart, context={"request": request})
            return self.success_response(
                message="Cart retrieved successfully.",
                data=serializer.data,
            )
        except Exception as e:
            logger.exception("Error fetching cart")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """Add or update item in cart."""
        try:
            cart = self._get_or_create_cart(request.user)
            serializer = CartItemSerializer(data=request.data, context={"request": request})

            if not serializer.is_valid():
                return self.error_response(
                    message="Validation error.",
                    errors=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            product = serializer.validated_data["product"]
            quantity = serializer.validated_data["quantity"]

            if not product.is_in_stock:
                return self.error_response(
                    message="Product is out of stock.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if quantity > product.quantity:
                return self.error_response(
                    message=f"Only {product.quantity} items available in stock.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart, product=product, defaults={"quantity": quantity}
            )
            if not created:
                cart_item.quantity = quantity  # update quantity if already exists
                cart_item.save()

            cart.refresh_from_db()
            cart_serializer = CartSerializer(cart, context={"request": request})
            return self.success_response(
                message="Item added to cart." if created else "Cart item updated.",
                data=cart_serializer.data,
                status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception("Error adding to cart")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request):
        """Clear all items from cart."""
        try:
            cart = self._get_or_create_cart(request.user)
            cart.items.all().delete()
            return self.success_response(message="Cart cleared successfully.")
        except Exception as e:
            logger.exception("Error clearing cart")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CartItemAPIView(APIResponse, APIView):
    """
    PATCH  /api/cart/items/<id>/   → Update quantity
    DELETE /api/cart/items/<id>/   → Remove single item
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_cart_item(self, pk, user):
        return CartItem.objects.select_related("product", "cart__user").get(
            pk=pk, cart__user=user
        )

    def patch(self, request, pk):
        try:
            item = self._get_cart_item(pk, request.user)
            quantity = request.data.get("quantity")

            if not quantity or int(quantity) < 1:
                return self.error_response(
                    message="Quantity must be at least 1.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            quantity = int(quantity)
            if quantity > item.product.quantity:
                return self.error_response(
                    message=f"Only {item.product.quantity} items available.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            item.quantity = quantity
            item.save()

            serializer = CartItemSerializer(item, context={"request": request})
            return self.success_response(
                message="Cart item updated.", data=serializer.data
            )
        except CartItem.DoesNotExist:
            return self.error_response(
                message="Cart item not found.", status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Error updating cart item")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            item = self._get_cart_item(pk, request.user)
            item.delete()
            return self.success_response(message="Item removed from cart.")
        except CartItem.DoesNotExist:
            return self.error_response(
                message="Cart item not found.", status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Error removing cart item")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─── Orders ───────────────────────────────────────────────────────────────────

class CartCheckoutAPIView(APIResponse, APIView):
    """
    POST /api/orders/checkout/
    Creates an order from the user's current cart.
    Body: { full_name, phone, address, city, postal_code }
    SSLCommerz payment will be initiated here in a future phase.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            cart = Cart.objects.prefetch_related("items__product").filter(user=request.user).first()
            if not cart or not cart.items.exists():
                return self.error_response(
                    message="Your cart is empty.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            serializer = OrderCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return self.error_response(
                    message="Validation error.",
                    errors=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Stock validation
            for item in cart.items.all():
                if item.quantity > item.product.quantity:
                    return self.error_response(
                        message=f"'{item.product.name}' only has {item.product.quantity} items left.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Create order
            order = Order.objects.create(
                user=request.user,
                total_amount=cart.total_price,
                **serializer.validated_data,
            )

            # Create order items & deduct stock
            order_items = []
            for item in cart.items.select_related("product").all():
                order_items.append(
                    OrderItem(
                        order=order,
                        product=item.product,
                        product_name=item.product.name,
                        product_sku=item.product.sku,
                        quantity=item.quantity,
                        unit_price=item.product.discounted_price,
                    )
                )
                item.product.quantity -= item.quantity
                item.product.save(update_fields=["quantity"])

            OrderItem.objects.bulk_create(order_items)
            cart.items.all().delete()  # clear cart after order

            response_serializer = OrderDetailSerializer(order)
            return self.success_response(
                message="Order placed successfully. Awaiting payment.",
                data=response_serializer.data,
                status_code=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.exception("Error during cart checkout")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BuyNowAPIView(APIResponse, APIView):
    """
    POST /api/orders/buy-now/
    Direct purchase for a single product (skips cart).
    Body: { product_id, quantity, full_name, phone, address, city, postal_code }
    SSLCommerz payment will be initiated here in a future phase.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            product_id = request.data.get("product_id")
            quantity = int(request.data.get("quantity", 1))

            if not product_id:
                return self.error_response(
                    message="product_id is required.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            product = Product.objects.filter(id=product_id, is_active=True).first()
            if not product:
                return self.error_response(
                    message="Product not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            if not product.is_in_stock or quantity > product.quantity:
                return self.error_response(
                    message=f"Only {product.quantity} items available.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            serializer = OrderCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return self.error_response(
                    message="Validation error.",
                    errors=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            total = product.discounted_price * quantity
            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                **serializer.validated_data,
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_sku=product.sku,
                quantity=quantity,
                unit_price=product.discounted_price,
            )

            product.quantity -= quantity
            product.save(update_fields=["quantity"])

            response_serializer = OrderDetailSerializer(order)
            return self.success_response(
                message="Order created successfully. Awaiting payment.",
                data=response_serializer.data,
                status_code=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.exception("Error during buy-now")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrderListAPIView(APIResponse, APIView):
    """
    GET /api/orders/
    List authenticated user's orders with pagination.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ProductPagination

    def get(self, request):
        try:
            queryset = (
                Order.objects.filter(user=request.user)
                .prefetch_related("items")
                .order_by("-created_at")
            )

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)
            serializer = OrderDetailSerializer(page, many=True)

            return self.success_response(
                message="Orders retrieved successfully.",
                data=serializer.data,
                meta={
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                },
            )
        except Exception as e:
            logger.exception("Error fetching orders")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrderDetailAPIView(APIResponse, APIView):
    """
    GET /api/orders/<order_id>/
    Retrieve a specific order by UUID.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.prefetch_related("items").get(
                order_id=order_id, user=request.user
            )
            serializer = OrderDetailSerializer(order)
            return self.success_response(
                message="Order retrieved successfully.", data=serializer.data
            )
        except Order.DoesNotExist:
            return self.error_response(
                message="Order not found.", status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception("Error fetching order detail")
            return self.error_response(
                message="Internal server error.",
                errors=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )