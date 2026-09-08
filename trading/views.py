from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import Order, Trade, Negotiation
from .trade_service import match_order
from certificates.models import GreenCertificate
from certificates.cert_share_service import freeze_shares, unfreeze_shares, get_available_shares
from accounts.models import UserProfile


@login_required
def order_list(request):
    orders = Order.objects.filter(status__in=['pending', 'partial']).select_related('user', 'certificate')
    my_orders = Order.objects.filter(user=request.user).select_related('certificate')
    return render(request, 'trading/order_list.html', {'orders': orders, 'my_orders': my_orders})


@login_required
def create_order(request):
    if request.method == 'POST':
        cert_id = request.POST.get('certificate')
        order_type = request.POST.get('order_type')
        shares = int(request.POST.get('shares', 0))
        price = float(request.POST.get('price', 0))
        days = int(request.POST.get('valid_days', 7))

        cert = get_object_or_404(GreenCertificate, pk=cert_id, status='active')
        profile = request.user.profile

        if shares <= 0 or price <= 0:
            messages.error(request, '份额和价格必须大于0')
            return redirect('trading:create_order')

        if order_type == 'sell':
            available = get_available_shares(request.user, cert)
            if shares > available:
                messages.error(request, f'可用份额不足，当前可用 {available} 份')
                return redirect('trading:create_order')
            freeze_shares(request.user, cert, shares)
        elif order_type == 'buy':
            total_cost = shares * price
            if total_cost > profile.points:
                messages.error(request, f'积分不足，需要 {total_cost}，当前 {profile.points}')
                return redirect('trading:create_order')
            profile.points -= int(total_cost)
            profile.save()

        order = Order.objects.create(
            user=request.user, order_type=order_type, certificate=cert,
            shares=shares, price_per_share=price,
            expire_time=timezone.now() + timedelta(days=days),
        )
        messages.success(request, '挂单成功')
        match_order(order)
        return redirect('trading:order_list')

    certs = GreenCertificate.objects.filter(status='active')
    return render(request, 'trading/create_order.html', {'certs': certs})





@login_required
def cancel_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status not in ('pending', 'partial'):
        messages.error(request, '该挂单无法取消')
        return redirect('trading:order_list')

    remaining = order.remaining
    if order.order_type == 'sell':
        unfreeze_shares(request.user, order.certificate, remaining)
    elif order.order_type == 'buy':
        refund = int(remaining * order.price_per_share)
        profile = request.user.profile
        profile.points += refund
        profile.save()

    order.status = 'cancelled'
    order.save()
    messages.success(request, '挂单已取消')
    return redirect('trading:order_list')


@login_required
def negotiate(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        msg = request.POST.get('message', '')
        price = float(request.POST.get('proposed_price', 0))
        Negotiation.objects.create(
            order=order, sender=request.user,
            message=msg, proposed_price=price,
        )
        messages.success(request, '议价请求已发送')
        return redirect('trading:order_list')
    negotiations = Negotiation.objects.filter(order=order)
    return render(request, 'trading/negotiate.html', {'order': order, 'negotiations': negotiations})


@login_required
def trade_history(request):
    trades = Trade.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    ).select_related('certificate', 'buyer', 'seller')
    return render(request, 'trading/trade_history.html', {'trades': trades})


@login_required
def manage_orders(request):
    """系统管理员查看并管理所有挂单"""
    if request.user.profile.role != 'admin':
        messages.error(request, '仅系统管理员可管理交易')
        return redirect('home')
    pending_orders = Order.objects.filter(
        status__in=['pending', 'partial']
    ).select_related('user', 'certificate').order_by('-created_at')
    all_trades = Trade.objects.select_related(
        'buyer', 'seller', 'certificate'
    ).order_by('-created_at')[:50]
    return render(request, 'trading/manage_orders.html', {
        'pending_orders': pending_orders,
        'all_trades': all_trades,
    })


@login_required
def force_cancel_order(request, pk):
    """系统管理员强制取消任意挂单"""
    if request.user.profile.role != 'admin':
        messages.error(request, '仅系统管理员可强制取消订单')
        return redirect('home')
    order = get_object_or_404(Order, pk=pk)
    if order.status not in ('pending', 'partial'):
        messages.error(request, '该挂单无法取消')
        return redirect('trading:manage_orders')

    remaining = order.remaining
    if order.order_type == 'sell':
        unfreeze_shares(order.user, order.certificate, remaining)
    elif order.order_type == 'buy':
        refund = int(remaining * order.price_per_share)
        profile = order.user.profile
        profile.points += refund
        profile.save()

    order.status = 'cancelled'
    order.save()
    messages.success(request, f'已强制取消 {order.user.username} 的挂单 #{order.pk}')
    return redirect('trading:manage_orders')
