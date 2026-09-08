from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from .models import PVDevice, PowerRecord, GreenCertificate, CertShare
from accounts.models import UserProfile
from blockchain.services import add_block
from .cert_share_service import distribute_shares


@login_required
def device_list(request):
    devices = PVDevice.objects.all()
    return render(request, 'certificates/device_list.html', {'devices': devices})


@login_required
def record_power(request):
    if request.user.profile.role != 'property':
        messages.error(request, '仅物业管理员可录入发电数据')
        return redirect('home')
    devices = PVDevice.objects.filter(status='normal')
    if request.method == 'POST':
        device_id = request.POST.get('device')
        date = request.POST.get('date')
        kwh = float(request.POST.get('kwh', 0))
        device = get_object_or_404(PVDevice, pk=device_id)
        max_kwh = device.max_daily_kwh()
        if kwh > max_kwh:
            messages.error(request, f'发电量超出理论最大值 {max_kwh:.1f}kWh（装机容量{device.capacity_kw}kW × 日照{settings.DEFAULT_SUNSHINE_HOURS}h），请核实数据')
            return render(request, 'certificates/record_power.html', {'devices': devices})
        if kwh <= 0:
            messages.error(request, '发电量必须大于0')
            return render(request, 'certificates/record_power.html', {'devices': devices})
        if PowerRecord.objects.filter(device=device, date=date).exists():
            messages.error(request, '该设备当日已有记录')
            return render(request, 'certificates/record_power.html', {'devices': devices})
        PowerRecord.objects.create(device=device, date=date, kwh=kwh, recorder=request.user)
        messages.success(request, f'成功录入 {device} {date} 发电量 {kwh}kWh')
        _try_generate_cert(device)
        return redirect('certificates:device_list')
    return render(request, 'certificates/record_power.html', {'devices': devices})


def _try_generate_cert(device):
    """当累计发电量达到1000kWh(1MWh)时自动生成绿证"""
    records = PowerRecord.objects.filter(device=device, is_valid=True)
    total = records.aggregate(s=Sum('kwh'))['s'] or 0
    existing_certs = GreenCertificate.objects.filter(device=device).count()
    available_kwh = total - existing_certs * 1000
    while available_kwh >= 1000:
        cert = GreenCertificate(device=device, total_kwh=1000, total_shares=1000)
        cert.save()
        add_block({
            'type': 'cert_generation',
            'cert_id': cert.cert_id,
            'device': str(device),
            'kwh': 1000,
            'timestamp': timezone.now().isoformat(),
        })
        distribute_shares(cert)
        available_kwh -= 1000



@login_required
def change_device_status(request, pk):
    """物业管理员变更设备运行状态"""
    if request.user.profile.role != 'property':
        messages.error(request, '仅物业管理员可变更设备状态')
        return redirect('certificates:device_list')
    device = get_object_or_404(PVDevice, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(PVDevice.STATUS_CHOICES):
        device.status = new_status
        device.save()
        messages.success(request, f'{device} 状态已更新为 {device.get_status_display()}')
    else:
        messages.error(request, '无效的状态')
    return redirect('certificates:device_list')


@login_required
def my_shares(request):
    shares = CertShare.objects.filter(owner=request.user).select_related('certificate').order_by('-is_frozen', 'certificate__cert_id', '-acquired_at')
    total_kwh = shares.aggregate(s=Sum('amount'))['s'] or 0
    co2_saved = total_kwh * settings.CO2_FACTOR
    return render(request, 'certificates/my_shares.html', {
        'shares': shares, 'total_kwh': total_kwh, 'co2_saved': co2_saved,
    })


@login_required
def cert_detail(request, cert_id):
    cert = get_object_or_404(GreenCertificate, cert_id=cert_id)
    shares = CertShare.objects.filter(certificate=cert)
    return render(request, 'certificates/cert_detail.html', {'cert': cert, 'shares': shares})


@login_required
def add_device(request):
    if request.user.profile.role not in ('property', 'admin'):
        messages.error(request, '无权限')
        return redirect('home')
    if request.method == 'POST':
        PVDevice.objects.create(
            name=request.POST['name'],
            building=request.POST['building'],
            capacity_kw=float(request.POST['capacity_kw']),
            installed_date=request.POST['installed_date'],
        )
        messages.success(request, '设备添加成功')
        return redirect('certificates:device_list')
    return render(request, 'certificates/add_device.html')
