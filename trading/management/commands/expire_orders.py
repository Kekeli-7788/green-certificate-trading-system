"""
定时清理已过期的挂单。

对每张已过期但仍为 pending / partial 的挂单：
  - 卖单：解冻剩余份额
  - 买单：退还剩余积分
  - 将状态标记为 expired

用法：python manage.py expire_orders
建议配置 cron 每 5~10 分钟执行一次。
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from trading.models import Order
from certificates.cert_share_service import unfreeze_shares


class Command(BaseCommand):
    help = '清理已过期的交易挂单：解冻份额、退还积分'

    def handle(self, *args, **options):
        now = timezone.now()
        expired_orders = Order.objects.filter(
            status__in=['pending', 'partial'],
            expire_time__lte=now,
        ).select_related('user', 'certificate')

        count = 0
        for order in expired_orders:
            remaining = order.remaining
            if remaining <= 0:
                order.status = 'expired'
                order.save()
                continue

            if order.order_type == 'sell':
                unfreeze_shares(order.user, order.certificate, remaining)
            elif order.order_type == 'buy':
                refund = int(remaining * order.price_per_share)
                profile = order.user.profile
                profile.points += refund
                profile.save()

            order.status = 'expired'
            order.save()
            count += 1

        self.stdout.write(self.style.SUCCESS(f'已处理 {count} 张过期挂单'))
