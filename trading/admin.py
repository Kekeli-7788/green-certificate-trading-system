from django.contrib import admin
from .models import Order, Trade, Negotiation


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'order_type', 'certificate', 'shares', 'filled_shares', 'price_per_share', 'status']
    list_filter = ['order_type', 'status']


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['buyer', 'seller', 'certificate', 'shares', 'price_per_share', 'total_price', 'created_at']


@admin.register(Negotiation)
class NegotiationAdmin(admin.ModelAdmin):
    list_display = ['order', 'sender', 'proposed_price', 'is_accepted', 'created_at']
