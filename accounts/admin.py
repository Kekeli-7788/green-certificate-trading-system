from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'unit_number', 'phone', 'area', 'points', 'is_verified']
    list_filter = ['role', 'is_verified']
    search_fields = ['user__username', 'unit_number', 'phone']
