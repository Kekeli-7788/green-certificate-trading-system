import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.conf import settings
from certificates.models import GreenCertificate, CertShare, PowerRecord, PVDevice
from trading.models import Trade, Order
from accounts.models import UserProfile
from .models import SystemConfig


@login_required
def personal_stats(request):
    shares = CertShare.objects.filter(owner=request.user)
    total_kwh = shares.aggregate(s=Sum('amount'))['s'] or 0
    co2_kg = total_kwh * settings.CO2_FACTOR
    trees = co2_kg / 18.3  # 一棵树年均吸收18.3kg CO2

    trades = Trade.objects.filter(buyer=request.user)
    buy_cost = trades.aggregate(s=Sum('total_price'))['s'] or 0
    sells = Trade.objects.filter(seller=request.user)
    sell_income = sells.aggregate(s=Sum('total_price'))['s'] or 0

    # 月度持有趋势（最近12个月）
    from django.utils import timezone
    from datetime import timedelta
    months = []
    for i in range(11, -1, -1):
        dt = timezone.now() - timedelta(days=30 * i)
        label = dt.strftime('%Y-%m')
        count = CertShare.objects.filter(
            owner=request.user, acquired_at__lte=dt
        ).aggregate(s=Sum('amount'))['s'] or 0
        months.append({'label': label, 'value': count})

    return render(request, 'stats/personal.html', {
        'total_kwh': total_kwh,
        'co2_kg': co2_kg,
        'trees': round(trees, 1),
        'buy_cost': buy_cost,
        'sell_income': sell_income,
        'profit': sell_income - buy_cost,
        'months_json': json.dumps(months, ensure_ascii=False),
    })


@login_required
def community_stats(request):
    if request.user.profile.role != 'admin':
        from django.contrib import messages
        messages.error(request, '仅系统管理员可查看社区统计')
        from django.shortcuts import redirect
        return redirect('home')

    total_devices = PVDevice.objects.count()
    total_power = PowerRecord.objects.filter(is_valid=True).aggregate(s=Sum('kwh'))['s'] or 0
    total_certs = GreenCertificate.objects.count()
    total_trades = Trade.objects.count()
    total_trade_shares = Trade.objects.aggregate(s=Sum('shares'))['s'] or 0
    total_residents = UserProfile.objects.filter(role='resident', is_verified=True).count()
    total_co2 = total_power * settings.CO2_FACTOR
    total_trees = total_co2 / 18.3

    # 月度发电量（过去12个月）
    from django.utils import timezone
    from datetime import timedelta
    power_months = []
    trade_months = []
    for i in range(11, -1, -1):
        start = (timezone.now() - timedelta(days=30 * (i + 1))).date()
        end = (timezone.now() - timedelta(days=30 * i)).date()
        label = end.strftime('%Y-%m')
        kwh = PowerRecord.objects.filter(
            is_valid=True, date__gte=start, date__lt=end
        ).aggregate(s=Sum('kwh'))['s'] or 0
        power_months.append({'label': label, 'value': round(kwh, 1)})
        tc = Trade.objects.filter(created_at__date__gte=start, created_at__date__lt=end).count()
        trade_months.append({'label': label, 'value': tc})

    return render(request, 'stats/community.html', {
        'total_devices': total_devices,
        'total_power': round(total_power, 1),
        'total_certs': total_certs,
        'total_trades': total_trades,
        'total_trade_shares': total_trade_shares,
        'total_residents': total_residents,
        'total_co2': round(total_co2, 1),
        'total_trees': round(total_trees, 1),
        'power_months_json': json.dumps(power_months, ensure_ascii=False),
        'trade_months_json': json.dumps(trade_months, ensure_ascii=False),
    })


# 系统参数默认值定义
CONFIG_DEFAULTS = {
    'CO2_FACTOR': {'value': 0.8, 'description': 'CO2减排系数(kg/kWh)'},
    'CERT_VALIDITY_YEARS': {'value': 5, 'description': '绿证有效期(年)'},
    'CERT_SPLIT_COUNT': {'value': 1000, 'description': '每张绿证拆分份额数'},
    'INITIAL_POINTS': {'value': 10000, 'description': '居民初始虚拟积分'},
    'DEFAULT_SUNSHINE_HOURS': {'value': 5, 'description': '默认日均日照时长(小时)'},
}


def _get_or_create_configs():
    """确保所有配置项存在，缺失则用默认值创建"""
    for key, info in CONFIG_DEFAULTS.items():
        SystemConfig.objects.get_or_create(
            key=key,
            defaults={'value': info['value'], 'description': info['description']},
        )
    return SystemConfig.objects.all()


@login_required
def system_config(request):
    """系统管理员配置系统运行参数"""
    if request.user.profile.role != 'admin':
        messages.error(request, '仅系统管理员可修改系统配置')
        return redirect('home')

    if request.method == 'POST':
        for config in _get_or_create_configs():
            val = request.POST.get(f'config_{config.key}')
            if val is not None:
                try:
                    config.value = float(val)
                    config.save()
                except ValueError:
                    messages.error(request, f'{config.description}的值无效')
                    return render(request, 'stats/system_config.html', {'configs': _get_or_create_configs()})
        messages.success(request, '系统配置已更新')
        return redirect('stats:system_config')

    configs = _get_or_create_configs()
    return render(request, 'stats/system_config.html', {'configs': configs})
