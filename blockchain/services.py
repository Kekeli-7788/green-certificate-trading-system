import time
from .models import Block


def add_block(data: dict) -> Block:
    """向简化版联盟链添加新区块"""
    last = Block.objects.order_by('-index').first()
    if last is None:
        index = 0
        previous_hash = '0' * 64
    else:
        index = last.index + 1
        previous_hash = last.hash

    timestamp = time.time()
    block_hash = Block.calculate_hash(index, timestamp, data, previous_hash)
    block = Block.objects.create(
        index=index,
        timestamp=timestamp,
        data=data,
        previous_hash=previous_hash,
        hash=block_hash,
    )
    return block


def verify_chain() -> bool:
    """验证区块链完整性"""
    blocks = Block.objects.order_by('index')
    for i, block in enumerate(blocks):
        expected = Block.calculate_hash(block.index, block.timestamp, block.data, block.previous_hash)
        if block.hash != expected:
            return False
        if i > 0 and block.previous_hash != blocks[i - 1].hash:
            return False
    return True
