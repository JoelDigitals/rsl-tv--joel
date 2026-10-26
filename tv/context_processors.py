from django.conf import settings
from django.utils import timezone
from .models import LiveStream, Schedule
from rsl_tv.broadcast_api import PLAYER_URL


def rsl_context(request):
    now = timezone.now()
    is_live = LiveStream.objects.filter(is_live=True).exists()
    current_show = Schedule.objects.filter(
        start_time__lte=now, end_time__gte=now, is_active=True
    ).first()
    return {
        'RSL_NAME': 'RSL',
        'RSL_SLOGAN': settings.RSL_CONFIG.get('SENDER_SLOGAN', ''),
        'RSL_COMPANY': settings.RSL_CONFIG.get('COMPANY', 'Joel Digitals'),
        'RSL_IS_LIVE': is_live,
        'RSL_CURRENT_SHOW': current_show,
        'RSL_PLAYER_URL': PLAYER_URL,
    }
