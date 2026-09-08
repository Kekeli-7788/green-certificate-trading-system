import hashlib
import json
import time
from django.db import models


class Block(models.Model):
    index = models.IntegerField('区块序号', unique=True)
    timestamp = models.FloatField('时间戳')
    data = models.JSONField('区块数据')
    previous_hash = models.CharField('前一区块哈希', max_length=128)
    hash = models.CharField('区块哈希', max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '区块'
        verbose_name_plural = verbose_name
        ordering = ['index']

    def __str__(self):
        return f'Block#{self.index} {self.hash[:16]}...'

    @staticmethod
    def calculate_hash(index, timestamp, data, previous_hash):
        raw = json.dumps({
            'index': index, 'timestamp': timestamp,
            'data': data, 'previous_hash': previous_hash,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
