from django.urls import path
from . import views

app_name = 'blockchain'
urlpatterns = [
    path('', views.block_list, name='block_list'),
    path('<int:index>/', views.block_detail, name='block_detail'),
]
