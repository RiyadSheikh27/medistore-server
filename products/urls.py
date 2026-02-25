from django.urls import path
from .views import (
    ProductCategoryListAPIView,
    ProductListAPIView,
    ProductDetailAPIView,
    ProductRelatedAPIView,
    LatestProductsAPIView,
    CartAPIView,
    CartItemAPIView,
    CartCheckoutAPIView,
    BuyNowAPIView,
    OrderListAPIView,
    OrderDetailAPIView,
)

app_name = "products"

"""Product URLs"""
product_urlpatterns = [
    path("", ProductListAPIView.as_view(), name="product-list"),
    path("latest/", LatestProductsAPIView.as_view(), name="product-latest"),
    path("categories/", ProductCategoryListAPIView.as_view(), name="category-list"),
    path("<slug:slug>/", ProductDetailAPIView.as_view(), name="product-detail"),
    path("<slug:slug>/related/", ProductRelatedAPIView.as_view(), name="product-related"),
]

"""Cart URLs"""
cart_urlpatterns = [
    path("", CartAPIView.as_view(), name="cart"),
    path("items/<int:pk>/", CartItemAPIView.as_view(), name="cart-item"),
]

"""Order URLs"""
order_urlpatterns = [
    path("", OrderListAPIView.as_view(), name="order-list"),
    path("checkout/", CartCheckoutAPIView.as_view(), name="cart-checkout"),
    path("buy-now/", BuyNowAPIView.as_view(), name="buy-now"),
    path("<uuid:order_id>/", OrderDetailAPIView.as_view(), name="order-detail"),
]