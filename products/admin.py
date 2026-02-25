from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.decorators import display

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


# ─── Inlines ─────────────────────────────────────────────────────────────────

class ProductMediaInline(TabularInline):
    model = ProductMedia
    extra = 1
    fields = ["image", "is_primary", "order", "preview"]
    readonly_fields = ["preview"]

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:4px;"/>', obj.image.url)
        return "—"
    preview.short_description = "Preview"


class AdditionalInfoInline(TabularInline):
    model = AdditionalInformation
    extra = 1
    fields = ["key", "value"]


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ["product", "quantity", "subtotal_display"]
    can_delete = False

    def subtotal_display(self, obj):
        return f"৳ {obj.subtotal:,.2f}"
    subtotal_display.short_description = "Subtotal"


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "product_sku", "quantity", "unit_price", "subtotal_display"]
    can_delete = False

    def subtotal_display(self, obj):
        return f"৳ {obj.subtotal:,.2f}"
    subtotal_display.short_description = "Subtotal"


# ─── Product Category ─────────────────────────────────────────────────────────

@admin.register(ProductCategory)
class ProductCategoryAdmin(ModelAdmin):
    list_display = ["thumbnail", "title", "slug", "product_count_display", "is_active", "created_at"]
    list_display_links = ["title"]
    list_filter = ["is_active"]
    search_fields = ["title", "slug"]
    prepopulated_fields = {"slug": ("title",)}
    list_per_page = 20

    @display(description="Image")
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;width:40px;object-fit:cover;border-radius:6px;"/>', obj.image.url)
        return "—"

    @display(description="Products")
    def product_count_display(self, obj):
        return obj.product_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(product_count=Count("products"))


# ─── Product ──────────────────────────────────────────────────────────────────

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = [
        "primary_image_thumb",
        "name",
        "category",
        "price_display",
        "discount",
        "discounted_price_display",
        "quantity",
        "stock_badge",
        "is_featured",
        "is_active",
        "created_at",
    ]
    list_display_links = ["name"]
    list_filter = ["is_active", "is_featured", "category"]
    search_fields = ["name", "sku"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]
    list_per_page = 20
    inlines = [ProductMediaInline, AdditionalInfoInline]
    fieldsets = (
        (
            "Basic Info",
            {"fields": ("name", "title", "slug", "category", "is_active", "is_featured")},
        ),
        (
            "Pricing & Inventory",
            {"fields": ("price", "discount", "sku", "quantity")},
        ),
        (
            "Description",
            {"fields": ("description",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @display(description="Image")
    def primary_image_thumb(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if image:
            return format_html(
                '<img src="{}" style="height:45px;width:45px;object-fit:cover;border-radius:6px;"/>',
                image.image.url,
            )
        return "—"

    @display(description="Price")
    def price_display(self, obj):
        return f"৳ {obj.price:,.2f}"

    @display(description="Final Price")
    def discounted_price_display(self, obj):
        if not obj.pk or obj.price is None:
            return "—"
        return f"৳ {obj.discounted_price:,.2f}"

    @display(description="Stock")
    def stock_badge(self, obj):
        if obj.quantity > 10:
            color = "#16a34a"
            label = "In Stock"
        elif obj.quantity > 0:
            color = "#d97706"
            label = f"Low ({obj.quantity})"
        else:
            color = "#dc2626"
            label = "Out of Stock"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
            color,
            label,
        )


# ─── Cart ─────────────────────────────────────────────────────────────────────

@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ["user", "total_items_display", "total_price_display", "created_at"]
    search_fields = ["user__email", "user__username"]
    readonly_fields = ["user", "total_items_display", "total_price_display", "created_at"]
    inlines = [CartItemInline]
    list_per_page = 20

    @display(description="Items")
    def total_items_display(self, obj):
        return obj.total_items

    @display(description="Total")
    def total_price_display(self, obj):
        return f"৳ {obj.total_price:,.2f}"


# ─── Order ────────────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = [
        "order_id_short",
        "user",
        "total_amount_display",
        "status_badge",
        "is_paid",
        "created_at",
    ]
    list_filter = ["status", "is_paid"]
    search_fields = ["user__email", "transaction_id", "order_id", "full_name", "phone"]
    readonly_fields = ["order_id", "user", "total_amount", "transaction_id", "is_paid", "paid_at", "created_at"]
    inlines = [OrderItemInline]
    list_per_page = 20
    fieldsets = (
        (
            "Order Info",
            {"fields": ("order_id", "user", "status", "total_amount", "created_at")},
        ),
        (
            "Shipping",
            {"fields": ("full_name", "phone", "address", "city", "postal_code")},
        ),
        (
            "Payment",
            {"fields": ("is_paid", "paid_at", "transaction_id"), "classes": ("collapse",)},
        ),
    )

    @display(description="Order ID")
    def order_id_short(self, obj):
        return str(obj.order_id)[:8].upper() + "..."

    @display(description="Total")
    def total_amount_display(self, obj):
        return f"৳ {obj.total_amount:,.2f}"

    @display(description="Status")
    def status_badge(self, obj):
        colors = {
            "pending":    "#6b7280",
            "confirmed":  "#2563eb",
            "processing": "#d97706",
            "shipped":    "#7c3aed",
            "delivered":  "#16a34a",
            "cancelled":  "#dc2626",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:999px;font-size:11px;">{}</span>',
            color,
            obj.get_status_display(),
        )