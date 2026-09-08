from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
import uuid


class PVDevice(models.Model):
    STATUS_CHOICES = [
        ('normal', '正常'), ('fault', '故障'), ('maintenance', '维护中')
    ]
    name = models.CharField('设备名称', max_length=100)
    building = models.CharField('所属楼栋', max_length=50)
    capacity_kw = models.FloatField('装机容量(kW)')
    status = models.CharField('运行状态', max_length=20, choices=STATUS_CHOICES, default='normal')
    installed_date = models.DateField('安装日期')

    class Meta:
        verbose_name = '光伏设备'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.building}-{self.name}'

    def max_daily_kwh(self):
        return self.capacity_kw * settings.DEFAULT_SUNSHINE_HOURS


class PowerRecord(models.Model):
    device = models.ForeignKey(PVDevice, on_delete=models.CASCADE, related_name='records')
    date = models.DateField('发电日期')
    kwh = models.FloatField('发电量(kWh)')
    recorder = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_valid = models.BooleanField('数据有效', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '发电记录'
        verbose_name_plural = verbose_name
        unique_together = ['device', 'date']

    def __str__(self):
        return f'{self.device} {self.date} {self.kwh}kWh'


class GreenCertificate(models.Model):
    STATUS_CHOICES = [
        ('active', '有效'), ('expired', '已过期'), ('used', '已使用'),
    ]
    cert_id = models.CharField('绿证编号', max_length=64, unique=True)
    device = models.ForeignKey(PVDevice, on_delete=models.CASCADE)
    total_kwh = models.FloatField('对应发电量(kWh)', default=1000)
    total_shares = models.IntegerField('总份额', default=1000)
    generated_date = models.DateField('生成日期', auto_now_add=True)
    expire_date = models.DateField('过期日期')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        verbose_name = '绿色电力证书'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.cert_id

    def save(self, *args, **kwargs):
        if not self.cert_id:
            self.cert_id = f'GEC-{timezone.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:8].upper()}'
        if not self.expire_date:
            self.expire_date = timezone.now().date() + timedelta(days=365 * settings.CERT_VALIDITY_YEARS)
        super().save(*args, **kwargs)


class CertShare(models.Model):
    SOURCE_CHOICES = [
        ('initial', '初始分配'), ('trade', '交易所得'),
    ]
    certificate = models.ForeignKey(GreenCertificate, on_delete=models.CASCADE, related_name='shares')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cert_shares')
    amount = models.IntegerField('份额数量')
    source = models.CharField('来源', max_length=20, choices=SOURCE_CHOICES, default='initial')
    is_frozen = models.BooleanField('是否冻结', default=False)
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '绿证份额'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.owner.username} 持有 {self.certificate.cert_id} x{self.amount}'

    @property
    def kwh_value(self):
        return self.amount

    @property
    def is_valid(self):
        return self.certificate.status == 'active'
