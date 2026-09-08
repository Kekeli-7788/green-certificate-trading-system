from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def home(request):
    from accounts.views import _ensure_profile
    profile = _ensure_profile(request.user)
    return render(request, 'home.html', {'role': profile.role})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('certificates/', include('certificates.urls')),
    path('trading/', include('trading.urls')),
    path('blockchain/', include('blockchain.urls')),
    path('stats/', include('stats.urls')),
]
