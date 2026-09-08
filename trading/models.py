from django.db import models
from django.contrib.auth.models import User
from certificates.models import GreenCertificate


class Order(models.Model):
    TYPE_CHOICES = [('buy', '买入'), ('sell', '卖出')]
    STATUS_CHOICES = [
        ('pending', '挂单中'), ('partial', '部分成交'),
        ('filled', '已成交'), ('cancelled', '已取消'), ('expired', '已过期'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_type = models.CharField('类型', max_length=10, choices=TYPE_CHOICES)
    certificate = models.ForeignKey(GreenCertificate, on_delete=models.CASCADE)
    shares = models.IntegerField('份额数量')
    filled_shares = models.IntegerField('已成交份额', default=0)
    price_per_share = models.FloatField('单价(积分/份)')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    expire_time = models.DateTimeField('过期时间')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '交易挂单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} {self.get_order_type_display()} {self.shares}份 @{self.price_per_share}'

    @property
    def remaining(self):
        return self.shares - self.filled_shares


class Trade(models.Model):
    buy_order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='buy_trades')
    sell_order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='sell_trades')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    certificate = models.ForeignKey(GreenCertificate, on_delete=models.CASCADE)
    shares = models.IntegerField('成交份额')
    price_per_share = models.FloatField('成交单价')
    total_price = models.FloatField('总价')
    block_hash = models.CharField('区块哈希', max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '成交记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'交易#{self.pk} {self.shares}份 @{self.price_per_share}'


class Negotiation(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='negotiations')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_negotiations')
    message = models.TextField('议价留言')
    proposed_price = models.FloatField('建议价格')
    is_accepted = models.BooleanField('是否接受', null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '议价记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
