from django.contrib import admin
from .models import PVDevice, PowerRecord, GreenCertificate, CertShare


@admin.register(PVDevice)
class PVDeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'building', 'capacity_kw', 'status', 'installed_date']
    list_filter = ['status', 'building']


@admin.register(PowerRecord)
class PowerRecordAdmin(admin.ModelAdmin):
    list_display = ['device', 'date', 'kwh', 'recorder', 'is_valid']
    list_filter = ['is_valid', 'date']


@admin.register(GreenCertificate)
class GreenCertificateAdmin(admin.ModelAdmin):
    list_display = ['cert_id', 'device', 'total_kwh', 'total_shares', 'generated_date', 'expire_date', 'status']
    list_filter = ['status']


@admin.register(CertShare)
class CertShareAdmin(admin.ModelAdmin):
    list_display = ['owner', 'certificate', 'amount', 'source', 'is_frozen', 'acquired_at']
    list_filter = ['source', 'is_frozen']
