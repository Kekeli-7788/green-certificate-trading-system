from django.urls import path
from . import views

app_name = 'trading'
urlpatterns = [
    path('orders/', views.order_list, name='order_list'),
    path('orders/create/', views.create_order, name='create_order'),
    path('orders/<int:pk>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<int:pk>/negotiate/', views.negotiate, name='negotiate'),
    path('orders/<int:pk>/force-cancel/', views.force_cancel_order, name='force_cancel_order'),
    path('manage/', views.manage_orders, name='manage_orders'),
    path('history/', views.trade_history, name='trade_history'),
]
