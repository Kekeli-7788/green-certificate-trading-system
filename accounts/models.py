from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('resident', '居民'),
        ('property', '物业管理员'),
        ('admin', '系统管理员'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default='resident')
    unit_number = models.CharField('居住单元号', max_length=50, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True)
    area = models.FloatField('居住面积(㎡)', default=0)
    points = models.IntegerField('虚拟积分', default=10000)
    is_verified = models.BooleanField('已审核', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '用户档案'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'
