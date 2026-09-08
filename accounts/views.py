from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .models import UserProfile


def _ensure_profile(user):
    """确保用户有profile，没有则自动创建"""
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(
            user=user, role='admin' if user.is_superuser else 'resident',
            points=settings.INITIAL_POINTS, is_verified=True,
        )


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        phone = request.POST.get('phone', '')
        unit_number = request.POST.get('unit_number', '')
        area = float(request.POST.get('area', 0) or 0)
        role = request.POST.get('role', 'resident')

        if not username or not password:
            messages.error(request, '用户名和密码不能为空')
            return render(request, 'accounts/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
            return render(request, 'accounts/register.html')

        user = User.objects.create_user(username=username, password=password)
        is_verified = role == 'admin' or role == 'property'
        UserProfile.objects.create(
            user=user, role=role, unit_number=unit_number,
            phone=phone, area=area,
            points=settings.INITIAL_POINTS,
            is_verified=is_verified,
        )
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, '注册成功！')
        return redirect('home')
    return render(request, 'accounts/register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            _ensure_profile(user)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home')
        messages.error(request, '用户名或密码错误')
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def profile_view(request):
    profile = _ensure_profile(request.user)
    if request.method == 'POST':
        profile.phone = request.POST.get('phone', profile.phone)
        profile.area = float(request.POST.get('area', profile.area) or profile.area)
        profile.save()
        messages.success(request, '资料更新成功')
    return render(request, 'accounts/profile.html', {'profile': profile})


@login_required
def verify_residents(request):
    profile = _ensure_profile(request.user)
    if profile.role not in ('admin', 'property'):
        messages.error(request, '无权限')
        return redirect('home')
    if request.method == 'POST':
        uid = request.POST.get('user_id')
        action = request.POST.get('action')
        try:
            p = UserProfile.objects.get(user_id=uid)
            if action == 'approve':
                p.is_verified = True
                p.save()
                messages.success(request, f'已审核通过 {p.user.username}')
            elif action == 'reject':
                p.user.delete()
                messages.success(request, '已拒绝该注册')
        except UserProfile.DoesNotExist:
            messages.error(request, '用户不存在')
    pending = UserProfile.objects.filter(role='resident', is_verified=False)
    return render(request, 'accounts/verify.html', {'pending': pending})
