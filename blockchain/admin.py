from django.contrib import admin
from .models import Block


@admin.register(Block)



class BlockAdmin(admin.ModelAdmin):
    list_display = ['index', 'hash', 'previous_hash', 'created_at']
    readonly_fields = ['index', 'timestamp', 'data', 'previous_hash', 'hash']
