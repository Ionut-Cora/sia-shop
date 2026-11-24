from django.contrib import admin
from .models import Order, OrderLineItem


class OrderLineItemAdminInline(admin.TabularInline):
    """Display purchased products within an order."""

    model = OrderLineItem
    extra = 0
    readonly_fields = (
        'product',
        'product_name',
        'product_size',
        'quantity',
        'lineitem_total',
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Manage customer orders in Django Admin."""

    inlines = (OrderLineItemAdminInline,)

    readonly_fields = (
        'order_number',
        'date',
        'order_total',
        'payment_status',
        'stripe_pid',
    )

    list_filter = ('payment_status',)

    list_display = (
        'order_number',
        'full_name',
        'email',
        'date',
        'order_total',
        'payment_status',
        'stripe_pid',
    )

    ordering = ('-date',)