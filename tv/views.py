"""
RSL TV – Views (vollständig überarbeitet)
Joel Digitals
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import timedelta
import random

from .models import (
    Video, Advertisement, Schedule, LiveStream, AdBreak, LiveAdBreak,
    AdBooking, AdBreakTemplate, AdVideo, PlaylistItem, PlaylistEntry,
    NewsItem, ContactMessage, Category, SenderLogo
)
from .forms import AdBookingForm, ContactForm
from .serializers import VideoSerializer, ScheduleSerializer, LiveStreamSerializer
from .mail import send_booking_confirmation, send_invoice, send_new_booking_admin


# ─── HAUPTSEITEN ──────────────────────────────────────────────────────────

def index(request):
    now = timezone.now()
    current_show = Schedule.objects.filter(
        start_time__lte=now, end_time__gte=now, is_active=True
    ).first()
    upcoming = Schedule.objects.filter(start_time__gte=now, is_active=True).order_by('start_time')[:5]
    live_stream = LiveStream.objects.filter(is_live=True).first()

    news = NewsItem.objects.filter(is_active=True)
    news = [n for n in news if not n.expires_at or n.expires_at >= now][:10]

    from django.conf import settings
    return render(request, 'tv/index.html', {
        'current_show': current_show,
        'upcoming': upcoming,
        'live_stream': live_stream,
        'news_items': news,
        'youtube_channel': settings.RSL_CONFIG.get('YOUTUBE_CHANNEL', ''),
        'twitch_channel': settings.RSL_CONFIG.get('TWITCH_CHANNEL', ''),
        'page': 'home',
    })


def program(request):
    now = timezone.now()
    today = now.date()
    days = []
    for i in range(7):
        day = today + timedelta(days=i)
        shows = Schedule.objects.filter(start_time__date=day, is_active=True).order_by('start_time')
        days.append({'date': day, 'shows': shows})
    return render(request, 'tv/program.html', {'days': days, 'today': today, 'page': 'program'})


def live(request):
    live_streams = LiveStream.objects.filter(is_live=True)
    upcoming_live = LiveStream.objects.filter(
        is_live=False, scheduled_start__gte=timezone.now()
    ).order_by('scheduled_start')[:5]
    return render(request, 'tv/live.html', {
        'live_streams': live_streams, 'upcoming_live': upcoming_live, 'page': 'live'
    })


def mediathek(request):
    category_slug = request.GET.get('kategorie')
    search = request.GET.get('q', '')
    videos = Video.objects.filter(is_active=True, allow_in_mediathek=True)  # Nur erlaubte Videos
    if category_slug:
        videos = videos.filter(category__slug=category_slug)
    if search:
        videos = videos.filter(title__icontains=search)
    categories = Category.objects.all()
    return render(request, 'tv/mediathek.html', {
        'videos': videos, 'categories': categories,
        'current_category': category_slug, 'search': search, 'page': 'mediathek'
    })


def werbung(request):
    packages = [
        {'id': 'starter',   'name': 'Starter',   'price': 49,  'plays': 50,   'duration': '30 Sek.', 'features': ['50 Einblendungen', 'Ganztägig', 'Basis-Reporting'], 'color': 'secondary'},
        {'id': 'basic',     'name': 'Basic',      'price': 99,  'plays': 150,  'duration': '30 Sek.', 'features': ['150 Einblendungen', 'Zeitslot wählbar', 'E-Mail Reporting'], 'color': 'primary'},
        {'id': 'standard',  'name': 'Standard',   'price': 199, 'plays': 400,  'duration': '60 Sek.', 'features': ['400 Einblendungen', 'Prime Time möglich', 'Reporting'], 'color': 'success', 'popular': True},
        {'id': 'premium',   'name': 'Premium',    'price': 399, 'plays': 1000, 'duration': '60 Sek.', 'features': ['1000 Einblendungen', 'Alle Zeitslots', 'Vollständiges Reporting', 'Priorität'], 'color': 'warning'},
        {'id': 'exclusive', 'name': 'Exklusiv',   'price': None,'plays': None, 'duration': 'Individuell', 'features': ['Individuelle Laufzeit', 'Exklusive Slots', 'Persönliche Beratung'], 'color': 'danger'},
    ]
    return render(request, 'tv/werbung.html', {'packages': packages, 'page': 'werbung'})


def werbung_buchen(request, package=None):
    if request.method == 'POST':
        form = AdBookingForm(request.POST)
        if form.is_valid():
            booking = form.save()
            # Buchungsbestätigung senden
            send_booking_confirmation(booking)
            booking.booking_confirmation_sent = True
            booking.save()
            # Admin benachrichtigen
            send_new_booking_admin(booking)
            messages.success(request, f'Buchungsanfrage erfolgreich! Buchungs-Nr.: {booking.id} – Wir senden Ihnen die Rechnung per E-Mail.')
            return redirect('werbung_success')
    else:
        form = AdBookingForm(initial={'package': package} if package else {})
    return render(request, 'tv/werbung_buchen.html', {'form': form, 'package': package, 'page': 'werbung'})


def werbung_success(request):
    return render(request, 'tv/werbung_success.html', {'page': 'werbung'})


def ueber_uns(request):
    return render(request, 'tv/ueber_uns.html', {'page': 'ueber'})


def kontakt(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nachricht erfolgreich übermittelt!')
            return redirect('kontakt')
    else:
        form = ContactForm()
    return render(request, 'tv/kontakt.html', {'form': form, 'page': 'kontakt'})


def impressum(request):
    return render(request, 'tv/impressum.html', {'page': 'impressum'})


def datenschutz(request):
    return render(request, 'tv/datenschutz.html', {'page': 'datenschutz'})


# ─── API ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
def api_playlist(request):
    """Hauptendpunkt für FFmpeg-Script"""
    now = timezone.now()

    # 1. Live-Werbepause?
    live = LiveStream.objects.filter(is_live=True).first()
    if live:
        ab = live.get_active_ad_break()
        if ab:
            block = ab.get_block() if ab.template else _build_default_block(ab.max_duration)
            return Response({
                'type': 'live_ad_break',
                'stream_url': live.stream_url,
                'ads': [{'url': v.video_url, 'title': v.title, 'duration': v.duration, 'ad_type': v.ad_type} for v in block],
                'live_title': live.title,
            })
        return Response({
            'type': 'live',
            'stream_url': live.stream_url,
            'embed_url': live.get_embed_url(),
            'title': live.title,
        })

    # 2. Sendeplan
    current = Schedule.objects.filter(
        start_time__lte=now, end_time__gte=now, is_active=True
    ).first()
    if current and current.video:
        elapsed = int((now - current.start_time).total_seconds())
        # Prüfe ob geplante Werbepause fällig
        due_break = current.ad_breaks.filter(
            time_offset_seconds__lte=elapsed, played=False
        ).order_by('time_offset_seconds').first()
        if due_break:
            block = due_break.get_block()
            due_break.played = True
            due_break.played_at = now
            due_break.save()
            return Response({
                'type': 'scheduled_ad_break',
                'video_url': current.video.get_stream_url(),
                'resume_at_seconds': elapsed,
                'title': current.title,
                'ads': [{'url': v.video_url, 'title': v.title, 'duration': v.duration, 'ad_type': v.ad_type} for v in block],
            })
        return Response({
            'type': 'scheduled',
            'video_url': current.video.get_stream_url(),
            'title': current.title,
            'start_seconds': elapsed,
            'ends_at': current.end_time.isoformat(),
        })

    # 3. Fallback Playlist
    pl = PlaylistItem.objects.filter(is_active=True).first()
    if pl:
        entries = list(PlaylistEntry.objects.filter(playlist=pl, video__is_active=True).select_related('video'))
        if pl.play_mode == 'random':
            random.shuffle(entries)
        items = []
        for i, e in enumerate(entries):
            items.append({'url': e.video.get_stream_url(), 'title': e.video.title, 'duration': e.video.duration})
            if (i + 1) % 3 == 0:
                block = _build_default_block(180)
                items.append({'type': 'ad_break', 'ads': [{'url': v.video_url, 'title': v.title, 'duration': v.duration, 'ad_type': v.ad_type} for v in block]})
        return Response({'type': 'playlist', 'items': items})

    return Response({'type': 'empty'})


def _build_default_block(max_duration=180):
    t = AdBreakTemplate(max_duration=max_duration, include_trailer=True, include_outro=True)
    return t.build_block()


@api_view(['GET'])
def api_current_show(request):
    now = timezone.now()
    live = LiveStream.objects.filter(is_live=True).first()
    live_ad = live.get_active_ad_break() if live else None
    current = Schedule.objects.filter(start_time__lte=now, end_time__gte=now, is_active=True).first()
    next_show = Schedule.objects.filter(start_time__gte=now, is_active=True).order_by('start_time').first()
    return Response({
        'is_live': live is not None,
        'live_ad_break': live_ad is not None,
        'live_title': live.title if live else None,
        'current_show': ScheduleSerializer(current).data if current else None,
        'next_show': ScheduleSerializer(next_show).data if next_show else None,
        'timestamp': now.isoformat(),
    })


@api_view(['GET'])
def api_news(request):
    now = timezone.now()
    news = [n for n in NewsItem.objects.filter(is_active=True) if not n.expires_at or n.expires_at >= now][:20]
    return Response([{'text': n.text} for n in news])


@api_view(['GET'])
def api_logo(request):
    """Gibt Logo-Info für FFmpeg zurück"""
    logo = SenderLogo.objects.filter(is_active=True).first()
    if logo:
        return Response(logo.get_ffmpeg_overlay())
    return Response({'error': 'no logo'}, status=404)


@api_view(['GET'])
def api_standby_image(request):
    """Gibt aktives Pausenbild zurück"""
    from .models import StandbyImage
    standby = StandbyImage.objects.filter(is_active=True).first()
    if standby and standby.image:
        return Response({
            'image_path': standby.image.path,
            'image_url': standby.image.url,
            'title': standby.title
        })
    return Response({'error': 'No standby image'}, status=404)


@require_GET
def iptv_playlist(request):
    from django.conf import settings
    youtube = settings.RSL_CONFIG.get('YOUTUBE_CHANNEL', '')
    m3u = "#EXTM3U\n"
    m3u += '#EXTINF:-1 tvg-id="RSL" tvg-name="RSL" group-title="Deutschland",RSL\n'
    m3u += f"{youtube}\n"
    return HttpResponse(m3u, content_type='application/x-mpegurl')


# ─── LIVE ADMIN API (AJAX für Admin-Panel) ────────────────────────────────

@staff_member_required
def live_start_ad(request, stream_id):
    """Startet Werbepause bei Live-Sendung (AJAX)"""
    stream = get_object_or_404(LiveStream, pk=stream_id)
    # Stoppe bestehende Werbepausen
    LiveAdBreak.objects.filter(live_stream=stream, is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    ab = LiveAdBreak.objects.create(live_stream=stream, max_duration=180)
    ab.start()
    return JsonResponse({'status': 'started', 'id': ab.id})


@staff_member_required
def live_stop_ad(request, stream_id):
    """Beendet Werbepause bei Live-Sendung (AJAX)"""
    stream = get_object_or_404(LiveStream, pk=stream_id)
    LiveAdBreak.objects.filter(live_stream=stream, is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    return JsonResponse({'status': 'stopped'})


# ─── TV ADMIN / REGIE PANEL ────────────────────────────────────────────────

from django.contrib.auth.decorators import login_required, user_passes_test

def is_director(user):
    """Prüft ob User Regie-Rechte hat - NUR SUPERUSER"""
    return user.is_superuser

@login_required
@user_passes_test(is_director)
def tv_admin_dashboard(request):
    """Regie-Dashboard"""
    from .models import Camera, LiveDirector, DirectorRoom
    live_streams = LiveStream.objects.filter(is_live=True)
    cameras = Camera.objects.filter(is_active=True)
    director_rooms = DirectorRoom.objects.filter(is_active=True)
    
    return render(request, 'tv/director_dashboard.html', {
        'live_streams': live_streams,
        'cameras': cameras,
        'director_rooms': director_rooms,
        'page': 'admin'
    })


@login_required
@user_passes_test(is_director)
def tv_admin_select_camera(request, stream_id, camera_id):
    """Wählt Kamera für Live-Stream aus (AJAX)"""
    from .models import Camera, LiveDirector
    stream = get_object_or_404(LiveStream, pk=stream_id)
    camera = get_object_or_404(Camera, pk=camera_id)
    
    director, created = LiveDirector.objects.get_or_create(live_stream=stream)
    director.selected_camera = camera
    director.save()
    
    return JsonResponse({
        'status': 'success',
        'camera': camera.name,
        'stream_url': camera.stream_url
    })


@login_required
@user_passes_test(is_director)
def director_room_dashboard(request, room_id):
    """Dashboard für einen spezifischen Regieraum"""
    from .models import DirectorRoom, DirectorRoomCamera, StandbyImage
    room = get_object_or_404(DirectorRoom, pk=room_id)
    room_cameras = DirectorRoomCamera.objects.filter(room=room).select_related('camera')
    standby_images = StandbyImage.objects.filter(is_active=True)
    
    return render(request, 'tv/director_room_dashboard.html', {
        'room': room,
        'room_cameras': room_cameras,
        'standby_images': standby_images,
        'page': 'admin'
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def start_stream_to_platform(request, room_id):
    """Startet Stream zu YouTube/Twitch von einem Regieraum"""
    from .models import DirectorRoom
    room = get_object_or_404(DirectorRoom, pk=room_id)
    platform = request.POST.get('platform')  # 'youtube' oder 'twitch'
    
    if platform not in ['youtube', 'twitch']:
        return JsonResponse({'status': 'error', 'message': 'Ungültige Plattform'}, status=400)
    
    # Prüfe ob Stream-Key vorhanden
    stream_key = room.youtube_stream_key if platform == 'youtube' else room.twitch_stream_key
    if not stream_key:
        return JsonResponse({
            'status': 'error', 
            'message': f'{platform.capitalize()} Stream-Key nicht konfiguriert'
        }, status=400)
    
    # Markiere als streaming
    room.is_streaming = True
    room.current_output = f'{platform}_streaming'
    room.save()
    
    return JsonResponse({
        'status': 'success',
        'platform': platform,
        'message': f'Stream zu {platform.capitalize()} gestartet'
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def stop_stream_from_platform(request, room_id):
    """Stoppt Stream von einem Regieraum"""
    from .models import DirectorRoom
    room = get_object_or_404(DirectorRoom, pk=room_id)
    
    room.is_streaming = False
    room.current_output = ''
    room.save()
    
    return JsonResponse({
        'status': 'success',
        'message': 'Stream gestoppt'
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def go_live_override(request, room_id):
    """Go Live - überlagert alle anderen Sendungen und Werbung"""
    from .models import DirectorRoom, Camera
    room = get_object_or_404(DirectorRoom, pk=room_id)
    camera_id = request.POST.get('camera_id')
    
    if not camera_id:
        return JsonResponse({'status': 'error', 'message': 'Keine Kamera ausgewählt'}, status=400)
    
    camera = get_object_or_404(Camera, pk=camera_id)
    
    # Erstelle oder aktualisiere LiveStream für diesen Raum
    live_stream, created = LiveStream.objects.get_or_create(
        title=f"LIVE aus {room.name}",
        defaults={
            'stream_url': camera.stream_url,
            'source_type': 'direct',
            'is_live': True,
        }
    )
    
    if not created:
        live_stream.stream_url = camera.stream_url
        live_stream.is_live = True
        live_stream.save()
    
    return JsonResponse({
        'status': 'success',
        'message': f'Live-Übertragung gestartet mit {camera.name}',
        'stream_id': live_stream.id
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def cut_out(request, room_id):
    """Cut Out - beendet Live-Übertragung"""
    from .models import DirectorRoom
    room = get_object_or_404(DirectorRoom, pk=room_id)
    
    # Beende alle Live-Streams für diesen Raum
    LiveStream.objects.filter(
        title__contains=room.name,
        is_live=True
    ).update(is_live=False)
    
    return JsonResponse({
        'status': 'success',
        'message': 'Live-Übertragung beendet'
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def show_standby_image(request, room_id):
    """Zeigt Pausenbild an"""
    from .models import DirectorRoom, StandbyImage
    room = get_object_or_404(DirectorRoom, pk=room_id)
    
    standby = StandbyImage.objects.filter(is_active=True).first()
    if not standby:
        return JsonResponse({'status': 'error', 'message': 'Kein Pausenbild verfügbar'}, status=404)
    
    room.current_output = f'standby_{standby.id}'
    room.save()
    
    return JsonResponse({
        'status': 'success',
        'message': 'Pausenbild angezeigt',
        'image_url': standby.image.url
    })