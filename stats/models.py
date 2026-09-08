from django.db import models


class SystemConfig(models.Model):
    """系统运行参数配置，仅系统管理员可修改"""
    key = models.CharField('参数名', max_length=50, unique=True)
    value = models.FloatField('参数值')
    description = models.CharField('说明', max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.key} = {self.value}'
