from accounts.models import UserProfile
from django.conf import settings


def user_profile(request):
    """确保模板中 user.profile 始终可用"""
    if request.user.is_authenticated:
        try:
            request.user.profile
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(
                user=request.user,
                role='admin' if request.user.is_superuser else 'resident',
                points=settings.INITIAL_POINTS,
                is_verified=True,
            )
    return {}
