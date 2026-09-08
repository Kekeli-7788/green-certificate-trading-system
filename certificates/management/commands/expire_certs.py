"""定时任务：检查绿证有效期，对到期绿证标记失效状态"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from certificates.models import GreenCertificate
from certificates.cert_share_service import delete_shares_by_cert


class Command(BaseCommand):
    help = '检查并处理过期绿证（建议每日凌晨执行）'

    def handle(self, *args, **options):
        today = timezone.now().date()
        expired = GreenCertificate.objects.filter(status='active', expire_date__lt=today)
        count = expired.count()
        for cert in expired:
            cert.status = 'expired'
            cert.save()
            delete_shares_by_cert(cert)
        self.stdout.write(self.style.SUCCESS(f'已处理 {count} 张过期绿证'))
