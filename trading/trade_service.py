"""
交易撮合服务 —— 价格优先、时间优先

撮合规则：
  1. 买单匹配卖单：卖价 <= 买价，按卖价从低到高、同价按时间从早到晚排列
  2. 卖单匹配买单：买价 >= 卖价，按买价从高到低、同价按时间从早到晚排列
  3. 成交价取挂单方（先到先得）的价格，即 candidate 的价格
  4. 撮合完成后若买方挂单价高于成交价，退还差额积分
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Order, Trade
from certificates.cert_share_service import transfer_frozen_shares, get_frozen_shares
from blockchain.services import add_block


@transaction.atomic
def match_order(new_order: Order) -> list[Trade]:
    """
    对新挂出的订单执行撮合，返回本次产生的 Trade 记录。

    整个撮合在一个事务中完成，通过 select_for_update 锁定 new_order，
    避免并发超卖；每轮成交后直接用锁行结果更新内存，不再 refresh_from_db。

    价格优先：买方取最低卖价，卖方取最高买价
    时间优先：同价时按 created_at 升序（先到先得）
    """
    # 锁定主动方订单，防止并发撮合同时修改
    new_order = Order.objects.select_for_update().get(pk=new_order.pk)
    if new_order.status not in ('pending', 'partial'):
        return []

    if new_order.order_type == 'buy':
        candidates = Order.objects.filter(
            certificate=new_order.certificate,
            order_type='sell',
            status__in=['pending', 'partial'],
            price_per_share__lte=new_order.price_per_share,
            expire_time__gt=timezone.now(),
        ).exclude(user=new_order.user).order_by('price_per_share', 'created_at')
    else:
        candidates = Order.objects.filter(
            certificate=new_order.certificate,
            order_type='buy',
            status__in=['pending', 'partial'],
            price_per_share__gte=new_order.price_per_share,
            expire_time__gt=timezone.now(),
        ).exclude(user=new_order.user).order_by('-price_per_share', 'created_at')

    trades: list[Trade] = []
    new_remaining = new_order.remaining  # 内存跟踪主动方剩余量，避免 refresh_from_db

    for candidate in candidates:
        if new_remaining <= 0:
            break
        # candidate 会在 execute_trade 内通过 select_for_update 锁定并校验，
        # 此处只需做轻量预判，避免对已无剩余的 candidate 调用 execute_trade
        candidate.refresh_from_db()
        if candidate.remaining <= 0:
            continue

        # 卖单撮合前预校验：卖方冻结份额必须足够，否则跳过
        if candidate.order_type == 'sell':
            frozen = get_frozen_shares(candidate.user, candidate.certificate)
            if frozen < candidate.remaining:
                continue

        match_shares = min(new_remaining, candidate.remaining)
        deal_price = candidate.price_per_share  # 挂单方价格优先
        try:
            trade = execute_trade(new_order, candidate, match_shares, deal_price)
        except ValueError:
            # execute_trade 校验失败（如并发导致份额不足），跳过该 candidate
            continue
        trades.append(trade)
        new_remaining -= match_shares

    return trades


@transaction.atomic
def execute_trade(active_order: Order, resting_order: Order,
                  shares: int, price: float) -> Trade:
    """
    执行一笔成交：转移份额与积分，上链存证。

    active_order  — 主动方（新挂单）
    resting_order — 挂单方（先挂在盘口的订单）
    shares        — 成交份额
    price         — 成交单价（取挂单方价格）
    """
    # 确定买卖双方
    if active_order.order_type == 'buy':
        buy_order, sell_order = active_order, resting_order
    else:
        buy_order, sell_order = resting_order, active_order

    buyer = buy_order.user
    seller = sell_order.user
    cert = buy_order.certificate
    total = shares * price

    # ---- 锁定关键行，防止并发超卖 ----
    buy_order = Order.objects.select_for_update().get(pk=buy_order.pk)
    sell_order = Order.objects.select_for_update().get(pk=sell_order.pk)
    buyer_profile = buyer.profile.__class__.objects.select_for_update().get(pk=buyer.profile.pk)
    seller_profile = seller.profile.__class__.objects.select_for_update().get(pk=seller.profile.pk)

    # ---- 校验挂单状态 ----
    for order in (buy_order, sell_order):
        if order.status not in ('pending', 'partial'):
            raise ValueError(f'订单 {order.pk} 状态为 {order.status}，无法成交')
        if order.remaining < shares:
            raise ValueError(f'订单 {order.pk} 剩余份额不足（剩余 {order.remaining}，需 {shares}）')

    # ---- 校验成交价格合理性 ----
    if price <= 0:
        raise ValueError(f'成交价格必须大于0，当前 {price}')

    # ---- 校验卖方冻结份额是否足够 ----
    frozen = get_frozen_shares(seller, cert)
    if frozen < shares:
        raise ValueError(
            f'卖方 {seller.username} 冻结份额不足（冻结 {frozen}，需 {shares}），'
            f'数据不一致，拒绝成交'
        )

    # ---- 转移份额 ----
    transfer_frozen_shares(seller, buyer, cert, shares)

    # ---- 积分转移：买方扣除、卖方收入 ----
    buyer_profile.points = F('points') - int(total)
    buyer_profile.save()
    buyer_profile.refresh_from_db()

    seller_profile.points = F('points') + int(total)
    seller_profile.save()
    seller_profile.refresh_from_db()

    # ---- 买方退还差额（挂单价高于成交价的部分） ----
    if buy_order.price_per_share > price:
        refund = int(shares * (buy_order.price_per_share - price))
        if refund > 0:
            buyer_profile.points = F('points') + refund
            buyer_profile.save()

    # ---- 更新挂单状态 ----
    for order in (buy_order, sell_order):
        order.filled_shares += shares
        order.status = 'filled' if order.filled_shares >= order.shares else 'partial'
        order.save()

    # ---- 区块链存证 ----
    block = add_block({
        'type': 'trade',
        'buyer': buyer.username,
        'seller': seller.username,
        'cert_id': cert.cert_id,
        'shares': shares,
        'price': price,
        'total': total,
        'timestamp': timezone.now().isoformat(),
    })

    # ---- 创建成交记录 ----
    trade = Trade.objects.create(
        buy_order=buy_order,
        sell_order=sell_order,
        buyer=buyer,
        seller=seller,
        certificate=cert,
        shares=shares,
        price_per_share=price,
        total_price=total,
        block_hash=block.hash,
    )
    return trade
