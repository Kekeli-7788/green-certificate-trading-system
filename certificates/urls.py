from django.urls import path
from . import views

app_name = 'certificates'
urlpatterns = [
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.add_device, name='add_device'),
    path('record/', views.record_power, name='record_power'),
    path('my-shares/', views.my_shares, name='my_shares'),
    path('devices/<int:pk>/status/', views.change_device_status, name='change_device_status'),
    path('detail/<str:cert_id>/', views.cert_detail, name='cert_detail'),
]
