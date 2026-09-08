from django.urls import path
from . import views

app_name = 'stats'
urlpatterns = [
    path('personal/', views.personal_stats, name='personal'),
    path('community/', views.community_stats, name='community'),
    path('config/', views.system_config, name='system_config'),
]
