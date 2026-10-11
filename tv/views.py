"""
RSL TV – Views (vereinigt)
Kombiniert: Basis-System + Erweiterte Features (Regieraum, Replay, Rundown)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q as DQ
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import timedelta
import random
import json
import subprocess
import threading
import signal
import os

from .models import (
    Video, Advertisement, Schedule, LiveStream, AdBreak, LiveAdBreak,
    AdBooking, AdBreakTemplate, AdVideo, PlaylistItem, PlaylistEntry,
    NewsItem, ContactMessage, Category, SenderLogo, StandbyImage,
    # Erweiterte Models
    DirectorRoom, DirectorRoomCamera, Camera, AudioSource, Scene, SceneAudioMix,
    Transition, ContentSegment, ShowRundown, ReplayClip, ReplayPlaylist, 
    ReplayPlaylistItem, ProgramRoom, VideoCache, StreamProcess, LiveDirector,
    PauseScreen, StreamOverlay, CutOutGraphic, StreamPreset,
    # Serien-System
    Series, Season, Episode
)
from .forms import AdBookingForm, ContactForm
from .serializers import VideoSerializer, ScheduleSerializer, LiveStreamSerializer
from .mail import send_booking_confirmation, send_invoice, send_new_booking_admin


# ══════════════════════════════════════════════════════════════════════════════
# HILFSFUNKTIONEN & DECORATORS
# ══════════════════════════════════════════════════════════════════════════════

def is_director(user):
    """Prüft ob User Regie-Rechte hat - NUR SUPERUSER"""
    return user.is_superuser


# ══════════════════════════════════════════════════════════════════════════════
# HAUPTSEITEN (Öffentlich)
# ══════════════════════════════════════════════════════════════════════════════

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

    # Twitch parent domain dynamisch setzen
    twitch_embed_url = None
    if live_stream and live_stream.source_type == 'twitch':
        host = request.get_host().split(':')[0]
        channel = live_stream.stream_url.split('twitch.tv/')[-1].strip('/')
        twitch_embed_url = f"https://player.twitch.tv/?channel={channel}&parent={host}&autoplay=true"

    from rsl_tv import broadcast_api as rsl_api
    api_current, api_upcoming = rsl_api.get_now_and_next(6)

    return render(request, 'tv/index.html', {
        'api_current': api_current,
        'api_upcoming': api_upcoming,
        'api_news': rsl_api.get_news()[:4],
        'api_library': rsl_api.get_library()[:8],
        'api_studios_live': [st for st in rsl_api.get_studios() if st['is_active']],
        'current_show': current_show,
        'upcoming': upcoming,
        'live_stream': live_stream,
        'news_items': news,
        'youtube_channel': settings.RSL_CONFIG.get('YOUTUBE_CHANNEL', ''),
        'twitch_channel': settings.RSL_CONFIG.get('TWITCH_CHANNEL', ''),
        'twitch_embed_url': twitch_embed_url,
        'page': 'home',
    })


def api_now_next(request):
    """Aktuelle und kommende Sendungen (für Live-Seite, ohne Neuladen)."""
    from rsl_tv import broadcast_api as rsl_api
    current, upcoming = rsl_api.get_now_and_next(6)
    broadcast = rsl_api.get_broadcast()

    def ser(s):
        return {
            'title': s['short_title'], 'series_title': s['series_title'], 'category': s['category'],
            'thumbnail': s['thumbnail'], 'start': s['start'].strftime('%H:%M'),
            'end': s['end'].strftime('%H:%M') if s['end'] else '',
            'start_iso': s['start'].isoformat(), 'end_iso': s['end'].isoformat() if s['end'] else '',
        }
    return JsonResponse({
        'is_live': bool(broadcast.get('is_live')),
        'ad_break_active': bool(broadcast.get('ad_break_active')),
        'current': ser(current) if current else None,
        'upcoming': [ser(s) for s in upcoming],
    })


def program(request):
    """TV-Programm – Daten aus der RSL Broadcast-API, Fallback: lokaler Sendeplan."""
    from rsl_tv import broadcast_api as rsl_api
    today = timezone.localdate()
    days = rsl_api.get_schedule_by_day()
    days = [d for d in days if d['date'] >= today]

    if not days:
        now = timezone.now()
        for i in range(7):
            day = today + timedelta(days=i)
            shows = [{
                'title': sh.title, 'short_title': sh.title, 'series_title': '',
                'category': sh.category.name if getattr(sh, 'category', None) else '',
                'thumbnail': '', 'program_id': None, 'is_repeat': False,
                'start': timezone.localtime(sh.start_time), 'end': timezone.localtime(sh.end_time),
                'is_now': sh.start_time <= now < sh.end_time, 'is_past': sh.end_time <= now,
            } for sh in Schedule.objects.filter(start_time__date=day, is_active=True).order_by('start_time')]
            if shows:
                days.append({'date': day, 'shows': shows})

    selected = request.GET.get('tag', '')
    current_day = next((d for d in days if d['date'].isoformat() == selected), days[0] if days else None)

    # Nur Sendungen verlinken, die es in der Mediathek gibt
    available = {p['id'] for p in rsl_api.get_programs() if p['video_type'] != 'ai_news'}
    if current_day:
        now = timezone.now()
        for sh in current_day['shows']:
            sh['in_mediathek'] = sh.get('program_id') in available
            if sh['is_now'] and sh['end']:
                total = (sh['end'] - sh['start']).total_seconds() or 1
                sh['progress'] = int(min(100, max(0, (now - sh['start']).total_seconds() / total * 100)))

    return render(request, 'tv/program.html', {
        'days': days, 'current_day': current_day, 'today': today, 'page': 'program',
    })


def live(request):
    from django.conf import settings
    
    live_streams = LiveStream.objects.filter(is_live=True)
    upcoming_live = LiveStream.objects.filter(
        is_live=False, scheduled_start__gte=timezone.now()
    ).order_by('scheduled_start')[:5]
    
    # YouTube & Twitch Channel IDs aus settings
    youtube_channel = settings.RSL_CONFIG.get('YOUTUBE_CHANNEL', '')
    twitch_channel = settings.RSL_CONFIG.get('TWITCH_CHANNEL', '')
    
    return render(request, 'tv/live.html', {
        'live_streams': live_streams, 
        'upcoming_live': upcoming_live,
        'youtube_channel': youtube_channel,
        'twitch_channel': twitch_channel,
        'page': 'live'
    })


def mediathek(request):
    category_slug = request.GET.get('kategorie')
    search = request.GET.get('q', '')
    videos = Video.objects.filter(is_active=True, allow_in_mediathek=True).order_by('-created_at')
    if category_slug:
        videos = videos.filter(category__slug=category_slug)
    if search:
        videos = videos.filter(title__icontains=search)
    categories = Category.objects.all()
    return render(request, 'tv/mediathek.html', {
        'videos': videos, 'categories': categories,
        'current_category': category_slug, 'search': search, 'page': 'mediathek'
    })


def video_player(request, video_id):
    """Video-Player-Seite"""
    video = get_object_or_404(Video, id=video_id, is_active=True)
    related_videos = Video.objects.filter(
        is_active=True, 
        allow_in_mediathek=True
    ).exclude(id=video_id).order_by('-created_at')[:6]
    
    return render(request, 'tv/video_player.html', {
        'video': video,
        'related_videos': related_videos,
        'page': 'mediathek'
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
            send_booking_confirmation(booking)
            booking.booking_confirmation_sent = True
            booking.save()
            send_new_booking_admin(booking)
            messages.success(request, f'Buchungsanfrage erfolgreich! Buchungs-Nr.: {booking.id}')
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


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPUNKTE (FFmpeg & Frontend)
# ══════════════════════════════════════════════════════════════════════════════

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

    ad_break_active = live_ad is not None
    ad_duration = 30
    if live_ad:
        remaining = (live_ad.started_at + timedelta(seconds=live_ad.max_duration) - now).total_seconds() if live_ad.started_at else 30
        ad_duration = max(int(remaining), 5)

    # Auch Programm-Regie-Werbepause berücksichtigen
    try:
        pr = ProgramRoom.objects.filter(pk=1).first()
        if pr and pr.ad_break_active:
            ad_break_active = True
            if pr.ad_break_ends_at:
                ad_duration = max(int((pr.ad_break_ends_at - now).total_seconds()), 5)
    except Exception:
        pass

    return Response({
        'is_live': live is not None,
        'ad_break_active': ad_break_active,
        'ad_duration': ad_duration,
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
    logo = SenderLogo.objects.filter(is_active=True).first()
    if logo:
        return Response(logo.get_ffmpeg_overlay())
    return Response({'error': 'no logo'}, status=404)


@api_view(['GET'])
def api_standby_image(request):
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


# ══════════════════════════════════════════════════════════════════════════════
# LIVE ADMIN API (AJAX für Admin-Panel)
# ══════════════════════════════════════════════════════════════════════════════

@staff_member_required
def live_start_ad(request, stream_id):
    stream = get_object_or_404(LiveStream, pk=stream_id)
    LiveAdBreak.objects.filter(live_stream=stream, is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    ab = LiveAdBreak.objects.create(live_stream=stream, max_duration=180)
    ab.start()
    return JsonResponse({'status': 'started', 'id': ab.id})


@staff_member_required
def live_stop_ad(request, stream_id):
    stream = get_object_or_404(LiveStream, pk=stream_id)
    LiveAdBreak.objects.filter(live_stream=stream, is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    return JsonResponse({'status': 'stopped'})


# ══════════════════════════════════════════════════════════════════════════════
# TV ADMIN / REGIE PANEL (Legacy & Basis)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_director)
def tv_admin_dashboard(request):
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
    room = get_object_or_404(DirectorRoom, pk=room_id)
    room_cameras = DirectorRoomCamera.objects.filter(room=room).select_related('camera').order_by('order')
    standby_images = StandbyImage.objects.filter(is_active=True)
    
    # Finde aktive Kamera (jetzt über die aktive Kamera des DirectorRoom)
    active_camera = None
    if room.active_camera:
        active_camera = room_cameras.filter(camera=room.active_camera).first()
    
    return render(request, 'tv/director_room_dashboard_enhanced.html', {
        'room': room,
        'room_cameras': room_cameras,
        'active_camera': active_camera,
        'standby_images': standby_images,
        'page': 'admin'
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def start_stream_to_platform(request, room_id):
    room = get_object_or_404(DirectorRoom, pk=room_id)
    platform = request.POST.get('platform')
    
    if platform not in ['youtube', 'twitch']:
        return JsonResponse({'status': 'error', 'message': 'Ungültige Plattform'}, status=400)
    
    stream_key = room.youtube_stream_key if platform == 'youtube' else room.twitch_stream_key
    if not stream_key:
        return JsonResponse({
            'status': 'error', 
            'message': f'{platform.capitalize()} Stream-Key nicht konfiguriert'
        }, status=400)
    
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
    room = get_object_or_404(DirectorRoom, pk=room_id)
    camera_id = request.POST.get('camera_id')
    
    if not camera_id:
        return JsonResponse({'status': 'error', 'message': 'Keine Kamera ausgewählt'}, status=400)
    
    camera = get_object_or_404(Camera, pk=camera_id)
    
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
    room = get_object_or_404(DirectorRoom, pk=room_id)
    
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


# ══════════════════════════════════════════════════════════════════════════════
# ERWEITERTER REGIERAUM (Multi-Kamera, Audio, Szenen)
# ══════════════════════════════════════════════════════════════════════════════

@staff_member_required
def director_room_view(request):
    """Haupt-Regieraum Interface (Erweitert)"""
    director_room = DirectorRoom.objects.first()
    
    if not director_room:
        director_room = DirectorRoom.objects.create(name="Hauptregie")
    
    cameras = director_room.cameras.filter(is_active=True).order_by('order')
    audio_sources = director_room.audio_sources.filter(is_active=True).order_by('order')
    scenes = Scene.objects.filter(is_active=True).order_by('order')
    transitions = Transition.objects.filter(is_active=True).order_by('name')
    
    context = {
        'director_room': director_room,
        'cameras': cameras,
        'audio_sources': audio_sources,
        'scenes': scenes,
        'transitions': transitions,
        'active_camera': director_room.active_camera,
        'preview_camera': director_room.preview_camera,
        'is_streaming': director_room.is_streaming_youtube or director_room.is_streaming_twitch,
        'page': 'director',
    }
    
    return render(request, 'tv/director_room.html', context)

@staff_member_required
@require_POST
def director_start_stream(request):
    """Startet den Stream aus dem erweiterten Regieraum - PYTHON STREAMER"""
    from python_streamer import get_stream_controller
    
    director_room = DirectorRoom.objects.first()
    
    if not director_room:
        return JsonResponse({'error': 'Kein Regieraum gefunden'}, status=404)
    
    youtube_key = request.POST.get('youtube_key', '')
    twitch_key = request.POST.get('twitch_key', '')
    
    if youtube_key:
        os.environ['YOUTUBE_STREAM_KEY'] = youtube_key
        director_room.is_streaming_youtube = True
    
    if twitch_key:
        os.environ['TWITCH_STREAM_KEY'] = twitch_key
        director_room.is_streaming_twitch = True
    
    director_room.save()
    
    try:
        controller = get_stream_controller(director_room=director_room)
        success = controller.start()  # RICHTIG: start() nicht start_stream()
        
        if success:
            director_room.append_log("🎬 Python-Stream gestartet")
            return JsonResponse({'success': True, 'message': 'Python-Stream gestartet'})
        else:
            return JsonResponse({'error': 'Stream konnte nicht gestartet werden'}, status=500)
    
    except Exception as e:
        director_room.append_log(f"❌ Stream-Start-Fehler: {e}")
        return JsonResponse({'error': f'Fehler beim Start: {str(e)}'}, status=500)


@staff_member_required
@require_POST
def director_stop_stream(request):
    """Stoppt den Stream aus dem erweiterten Regieraum - PYTHON STREAMER"""
    from python_streamer import get_stream_controller, reset_stream_controller
    
    director_room = DirectorRoom.objects.first()
    
    if not director_room:
        return JsonResponse({'error': 'Kein Regieraum gefunden'}, status=404)
    
    try:
        controller = get_stream_controller()
        if controller and controller.is_running:
            controller.stop()  # RICHTIG: stop() nicht stop_stream()
            director_room.append_log("⏹️ Python-Stream gestoppt")
        
        reset_stream_controller()
        
    except Exception as e:
        director_room.append_log(f"⚠️ Stop-Fehler: {e}")
    
    director_room.is_streaming_youtube = False
    director_room.is_streaming_twitch = False
    director_room.save()
    
    return JsonResponse({'success': True, 'message': 'Stream gestoppt'})


@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_start_stream(request):
    """Startet Stream über python_streamer.py - zu YouTube und/oder Twitch"""
    from python_streamer import get_stream_controller
    import os
    
    room, _ = ProgramRoom.objects.get_or_create(pk=1)
    
    youtube_key = request.POST.get('youtube_key', '').strip()
    twitch_key = request.POST.get('twitch_key', '').strip()
    
    if youtube_key:
        room.youtube_stream_key = youtube_key
        os.environ['YOUTUBE_STREAM_KEY'] = youtube_key
    if twitch_key:
        room.twitch_stream_key = twitch_key
        os.environ['TWITCH_STREAM_KEY'] = twitch_key
    
    room.save()
    
    if not (youtube_key or room.youtube_stream_key) and not (twitch_key or room.twitch_stream_key):
        room.append_log("❌ Keine Stream-Keys konfiguriert!")
        return JsonResponse({'success': False, 'error': 'Bitte mindestens einen Stream-Key eingeben!'}, status=400)
    
    try:
        if youtube_key or room.youtube_stream_key:
            room.is_streaming_youtube = True
            os.environ['YOUTUBE_STREAM_KEY'] = room.youtube_stream_key
        if twitch_key or room.twitch_stream_key:
            room.is_streaming_twitch = True
            os.environ['TWITCH_STREAM_KEY'] = room.twitch_stream_key
        
        room.save()
        room.append_log("🎬 Starte Python-Streamer...")
        
        controller = get_stream_controller(program_room=room)
        success = controller.start()  # RICHTIG: start() nicht start_stream()
        
        if not success:
            room.is_streaming_youtube = False
            room.is_streaming_twitch = False
            room.save()
            room.append_log("❌ Stream-Start fehlgeschlagen!")
            return JsonResponse({'success': False, 'error': 'Stream-Start fehlgeschlagen'}, status=500)
        
        platforms = []
        if room.is_streaming_youtube:
            platforms.append('YouTube')
        if room.is_streaming_twitch:
            platforms.append('Twitch')
        
        room.append_log(f"✅ Stream läuft auf: {' & '.join(platforms)}")
        return JsonResponse({'success': True, 'message': f'Stream gestartet auf {" & ".join(platforms)}!', 'platforms': platforms})
        
    except Exception as e:
        room.is_streaming_youtube = False
        room.is_streaming_twitch = False
        room.save()
        room.append_log(f"❌ FEHLER: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Fehler: {str(e)}'}, status=500)


@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_stop_stream(request):
    """Stoppt den laufenden Python-Stream"""
    from python_streamer import get_stream_controller, reset_stream_controller
    
    room, _ = ProgramRoom.objects.get_or_create(pk=1)

    try:
        controller = get_stream_controller()
        if controller and controller.is_running:
            controller.stop()  # RICHTIG: stop() nicht stop_stream()
            room.append_log("⏹ Python-Stream gestoppt")
        
        reset_stream_controller()
        
    except Exception as e:
        room.append_log(f"⏹ Stream-Stop-Fehler: {e}")

    room.is_streaming_youtube = False
    room.is_streaming_twitch = False
    room.ffmpeg_pid = None
    room.ad_break_active = False
    room.save()

    return JsonResponse({'status': 'success', 'message': 'Stream gestoppt'})

@staff_member_required
@require_POST
def director_switch_camera(request):
    """Wechselt die aktive Kamera mit optionalem Übergang"""
    from python_streamer import get_stream_controller
    
    director_room = DirectorRoom.objects.first()
    camera_id = request.POST.get('camera_id')
    transition = request.POST.get('transition', 'cut')
    
    if not director_room:
        return JsonResponse({'error': 'Kein Regieraum gefunden'}, status=404)
    
    try:
        # Finde Kamera
        room_camera = DirectorRoomCamera.objects.get(
            room=director_room,
            camera__id=camera_id
        )
        
        # Deaktiviere alle anderen Kameras
        DirectorRoomCamera.objects.filter(room=director_room).update(is_active=False)
        
        # Aktiviere gewählte Kamera
        room_camera.is_active = True
        room_camera.save()
        
        # Log
        director_room.append_log(f"📹 Kamera gewechselt: {room_camera.camera.name} ({transition})")
        
        # Wenn Stream läuft, Video-Quelle neu laden (RICHTIGE METHODE!)
        controller = get_stream_controller()
        if controller and controller.is_running:
            controller.setup_video_source()  # Diese Methode existiert!
            director_room.append_log(f"🔄 Video-Quelle aktualisiert")
        
        return JsonResponse({
            'success': True,
            'camera': {
                'id': room_camera.camera.id,
                'name': room_camera.camera.name,
            },
            'transition': transition
        })
        
    except DirectorRoomCamera.DoesNotExist:
        return JsonResponse({'error': 'Kamera nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_GET
def director_camera_preview(request, room_id, camera_id):
    """Liefert Vorschau-Frame einer Kamera als JPEG"""
    import cv2
    import numpy as np
    import base64
    from io import BytesIO
    
    try:
        room = get_object_or_404(DirectorRoom, pk=room_id)
        room_camera = DirectorRoomCamera.objects.get(
            room=room,
            camera__id=camera_id
        )
        
        camera = room_camera.camera
        
        # Frame von Kamera holen
        frame = None
        
        if camera.camera_type == 'webcam':
            device_id = int(camera.source_url) if camera.source_url.isdigit() else 0
            cap = cv2.VideoCapture(device_id)
            ret, frame = cap.read()
            cap.release()
            
        elif camera.camera_type == 'url':
            cap = cv2.VideoCapture(camera.source_url)
            ret, frame = cap.read()
            cap.release()
            
        elif camera.camera_type == 'image':
            if camera.source_file:
                frame = cv2.imread(camera.source_file.path)
        
        # Falls kein Frame, erstelle Platzhalter
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, camera.name, (50, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Skaliere auf Vorschau-Größe
        frame = cv2.resize(frame, (320, 180))
        
        # Konvertiere zu JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        # Als Base64
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return JsonResponse({
            'success': True,
            'image': f'data:image/jpeg;base64,{img_base64}',
            'camera': {
                'id': camera.id,
                'name': camera.name,
                'type': camera.camera_type
            }
        })
        
    except Exception as e:
        # Fehler-Frame
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        cv2.putText(frame, 'ERROR', (100, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return JsonResponse({
            'success': False,
            'image': f'data:image/jpeg;base64,{img_base64}',
            'error': str(e)
        })
    director_room = DirectorRoom.objects.first()
    camera_id = request.POST.get('camera_id')
    use_transition = request.POST.get('use_transition', 'true') == 'true'
    
    try:
        camera = Camera.objects.get(id=camera_id)
        director_room.switch_to_camera(camera, use_transition)
        
        return JsonResponse({
            'success': True,
            'camera': {
                'id': camera.id,
                'name': camera.name,
            }
        })
    
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Kamera nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def director_set_preview(request):
    """Setzt die Preview-Kamera"""
    director_room = DirectorRoom.objects.first()
    camera_id = request.POST.get('camera_id')
    
    try:
        camera = Camera.objects.get(id=camera_id) if camera_id else None
        director_room.preview_camera = camera
        director_room.save()
        
        return JsonResponse({
            'success': True,
            'camera': {
                'id': camera.id if camera else None,
                'name': camera.name if camera else 'Keine',
            }
        })
    
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Kamera nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def director_toggle_audio(request):
    """Schaltet Audio-Quelle an/aus"""
    audio_id = request.POST.get('audio_id')
    
    try:
        audio = AudioSource.objects.get(id=audio_id)
        audio.is_muted = not audio.is_muted
        audio.save()
        
        return JsonResponse({
            'success': True,
            'is_muted': audio.is_muted,
            'audio': {
                'id': audio.id,
                'name': audio.name,
                'is_muted': audio.is_muted,
            }
        })
    
    except AudioSource.DoesNotExist:
        return JsonResponse({'error': 'Audio-Quelle nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def director_set_audio_volume(request):
    """Setzt Audio-Lautstärke"""
    audio_id = request.POST.get('audio_id')
    volume = int(request.POST.get('volume', 100))
    
    try:
        audio = AudioSource.objects.get(id=audio_id)
        audio.volume = max(0, min(200, volume))
        audio.save()
        
        return JsonResponse({
            'success': True,
            'volume': audio.volume,
        })
    
    except AudioSource.DoesNotExist:
        return JsonResponse({'error': 'Audio-Quelle nicht gefunden'}, status=404)


@staff_member_required
@require_GET
def director_stream_log(request):
    """Gibt Stream-Log zurück"""
    director_room = DirectorRoom.objects.first()
    
    if not director_room:
        return JsonResponse({'log': ''})
    
    return JsonResponse({
        'log': director_room.stream_log or '',
        'is_streaming': director_room.is_streaming_youtube or director_room.is_streaming_twitch,
    })


@staff_member_required
@require_POST
def scene_activate(request):
    """Aktiviert eine Szene"""
    scene_id = request.POST.get('scene_id')
    director_room = DirectorRoom.objects.first()
    
    try:
        scene = Scene.objects.get(id=scene_id)
        
        director_room.active_camera = scene.camera
        director_room.active_scene = scene
        director_room.save()
        
        return JsonResponse({
            'success': True,
            'scene': {
                'id': scene.id,
                'name': scene.name,
                'camera': scene.camera.name,
            }
        })
    
    except Scene.DoesNotExist:
        return JsonResponse({'error': 'Szene nicht gefunden'}, status=404)


@staff_member_required
def scenes_view(request):
    """Szenen-Verwaltung"""
    scenes = Scene.objects.filter(is_active=True).order_by('order')
    cameras = Camera.objects.filter(is_active=True)
    audio_sources = AudioSource.objects.filter(is_active=True)
    
    context = {
        'scenes': scenes,
        'cameras': cameras,
        'audio_sources': audio_sources,
        'page': 'scenes',
    }
    
    return render(request, 'tv/scenes.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# REPLAY STUDIO
# ══════════════════════════════════════════════════════════════════════════════

@staff_member_required
def replay_studio_view(request):
    """Replay-Studio Interface"""
    clips = ReplayClip.objects.all().order_by('-recorded_at')
    playlists = ReplayPlaylist.objects.all().order_by('-created_at')
    
    tag_filter = request.GET.get('tag', '')
    if tag_filter:
        clips = clips.filter(tags__icontains=tag_filter)
    
    if request.GET.get('favorites') == '1':
        clips = clips.filter(is_favorite=True)
    
    context = {
        'clips': clips[:50],
        'playlists': playlists[:20],
        'all_tags': _get_all_replay_tags(),
        'page': 'replay',
    }
    
    return render(request, 'tv/replay_studio.html', context)


def _get_all_replay_tags():
    """Extrahiert alle verwendeten Tags"""
    clips = ReplayClip.objects.exclude(tags='')
    tags = set()
    
    for clip in clips:
        if clip.tags:
            tags.update([t.strip() for t in clip.tags.split(',')])
    
    return sorted(tags)


@staff_member_required
@require_POST
def replay_create_clip(request):
    """Erstellt neuen Replay-Clip"""
    director_room = DirectorRoom.objects.first()
    
    title = request.POST.get('title', 'Replay')
    duration = int(request.POST.get('duration', 30))
    
    clip = ReplayClip.objects.create(
        title=title,
        duration=duration,
        source_camera=director_room.active_camera if director_room else None,
        created_by=request.user,
    )
    
    return JsonResponse({
        'success': True,
        'clip': {
            'id': clip.id,
            'title': clip.title,
            'duration': clip.duration,
        }
    })


@staff_member_required
@require_POST
def replay_play_clip(request):
    """Spielt Replay-Clip ab"""
    clip_id = request.POST.get('clip_id')
    
    try:
        clip = ReplayClip.objects.get(id=clip_id)
        
        clip.times_played += 1
        clip.save()
        
        return JsonResponse({
            'success': True,
            'clip': {
                'id': clip.id,
                'title': clip.title,
            }
        })
    
    except ReplayClip.DoesNotExist:
        return JsonResponse({'error': 'Clip nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def replay_toggle_favorite(request):
    """Toggled Favoriten-Status"""
    clip_id = request.POST.get('clip_id')
    
    try:
        clip = ReplayClip.objects.get(id=clip_id)
        clip.is_favorite = not clip.is_favorite
        clip.save()
        
        return JsonResponse({
            'success': True,
            'is_favorite': clip.is_favorite,
        })
    
    except ReplayClip.DoesNotExist:
        return JsonResponse({'error': 'Clip nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def replay_delete_clip(request):
    """Löscht Replay-Clip"""
    clip_id = request.POST.get('clip_id')
    
    try:
        clip = ReplayClip.objects.get(id=clip_id)
        
        if clip.video_file:
            try:
                os.remove(clip.video_file.path)
            except Exception:
                pass
        
        clip.delete()
        
        return JsonResponse({
            'success': True,
        })
    
    except ReplayClip.DoesNotExist:
        return JsonResponse({'error': 'Clip nicht gefunden'}, status=404)


# ══════════════════════════════════════════════════════════════════════════════
# RUNDOWN-PLANUNG
# ══════════════════════════════════════════════════════════════════════════════

@staff_member_required
def rundown_planner_view(request):
    """Rundown-Planungs-Interface"""
    rundowns = ShowRundown.objects.all().order_by('-show_date')
    
    now = timezone.now()
    active_rundown = ShowRundown.objects.filter(is_live=True).first()
    upcoming_rundown = ShowRundown.objects.filter(
        show_date__gte=now,
        is_live=False
    ).order_by('show_date').first()
    
    context = {
        'rundowns': rundowns[:20],
        'active_rundown': active_rundown,
        'upcoming_rundown': upcoming_rundown,
        'page': 'rundown',
    }
    
    return render(request, 'tv/rundown_planner.html', context)


@staff_member_required
def rundown_detail_view(request, rundown_id):
    """Detailansicht eines Rundowns"""
    rundown = get_object_or_404(ShowRundown, id=rundown_id)
    segments = rundown.segments.all().order_by('order')
    
    total_duration = segments.aggregate(Sum('planned_duration'))['planned_duration__sum'] or 0
    
    context = {
        'rundown': rundown,
        'segments': segments,
        'total_duration': total_duration,
        'page': 'rundown',
    }
    
    return render(request, 'tv/rundown_detail.html', context)


@staff_member_required
@require_POST
def rundown_create(request):
    """Erstellt neuen Rundown"""
    title = request.POST.get('title')
    show_date_str = request.POST.get('show_date')
    
    try:
        from datetime import datetime
        show_date = datetime.fromisoformat(show_date_str)
        
        rundown = ShowRundown.objects.create(
            title=title,
            show_date=show_date,
            created_by=request.user,
        )
        
        return JsonResponse({
            'success': True,
            'rundown': {
                'id': rundown.id,
                'title': rundown.title,
            }
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@staff_member_required
@require_POST
def rundown_add_segment(request):
    """Fügt Segment zu Rundown hinzu"""
    rundown_id = request.POST.get('rundown_id')
    
    try:
        rundown = ShowRundown.objects.get(id=rundown_id)
        
        segment = ContentSegment.objects.create(
            rundown=rundown,
            title=request.POST.get('title', 'Neues Segment'),
            segment_type=request.POST.get('segment_type', 'other'),
            planned_duration=int(request.POST.get('duration', 300)),
            order=rundown.segments.count(),
            script=request.POST.get('script', ''),
        )
        
        rundown.calculate_total_duration()
        
        return JsonResponse({
            'success': True,
            'segment': {
                'id': segment.id,
                'title': segment.title,
                'duration': segment.planned_duration,
            }
        })
    
    except ShowRundown.DoesNotExist:
        return JsonResponse({'error': 'Rundown nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def rundown_reorder_segments(request):
    """Ändert Reihenfolge der Segmente"""
    segment_ids = json.loads(request.POST.get('segment_ids', '[]'))
    
    for index, segment_id in enumerate(segment_ids):
        try:
            segment = ContentSegment.objects.get(id=segment_id)
            segment.order = index
            segment.save()
        except ContentSegment.DoesNotExist:
            pass
    
    return JsonResponse({'success': True})


@staff_member_required
@require_POST
def rundown_start(request):
    """Startet Rundown-Wiedergabe"""
    rundown_id = request.POST.get('rundown_id')
    
    try:
        rundown = ShowRundown.objects.get(id=rundown_id)
        rundown.is_live = True
        rundown.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Rundown "{rundown.title}" gestartet',
        })
    
    except ShowRundown.DoesNotExist:
        return JsonResponse({'error': 'Rundown nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def rundown_stop(request):
    """Stoppt Rundown-Wiedergabe"""
    rundown_id = request.POST.get('rundown_id')
    
    try:
        rundown = ShowRundown.objects.get(id=rundown_id)
        rundown.is_live = False
        rundown.current_segment = None
        rundown.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Rundown gestoppt',
        })
    
    except ShowRundown.DoesNotExist:
        return JsonResponse({'error': 'Rundown nicht gefunden'}, status=404)


@staff_member_required
@require_POST
def rundown_next_segment(request):
    """Springt zum nächsten Segment"""
    rundown_id = request.POST.get('rundown_id')
    
    try:
        rundown = ShowRundown.objects.get(id=rundown_id)
        
        if not rundown.current_segment:
            first_segment = rundown.segments.order_by('order').first()
            rundown.current_segment = first_segment
        else:
            current_order = rundown.current_segment.order
            next_segment = rundown.segments.filter(order__gt=current_order).order_by('order').first()
            rundown.current_segment = next_segment
        
        rundown.save()
        
        return JsonResponse({
            'success': True,
            'current_segment': {
                'id': rundown.current_segment.id if rundown.current_segment else None,
                'title': rundown.current_segment.title if rundown.current_segment else None,
            }
        })
    
    except ShowRundown.DoesNotExist:
        return JsonResponse({'error': 'Rundown nicht gefunden'}, status=404)


# ══════════════════════════════════════════════════════════════════════════════
# PROGRAMM-REGIERAUM (24/7 Streaming)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_director)
def program_room_dashboard(request):
    """Programm-Regieraum: Sendeplan-Stream steuern"""
    room, created = ProgramRoom.objects.get_or_create(pk=1)
    now = timezone.now()

    current_show = Schedule.objects.filter(
        start_time__lte=now, end_time__gte=now, is_active=True
    ).first()
    upcoming_shows = Schedule.objects.filter(
        start_time__gte=now, is_active=True
    ).order_by('start_time')[:10]

    cache_status = []
    for show in Schedule.objects.filter(
        start_time__gte=now - timedelta(hours=1),
        start_time__lte=now + timedelta(hours=6),
        is_active=True, video__isnull=False
    ).select_related('video').order_by('start_time'):
        cache = getattr(show.video, 'cache', None)
        cache_status.append({
            'show': show,
            'cache': cache,
        })

    recent_processes = StreamProcess.objects.filter(
        program_room=room
    ).order_by('-started_at')[:10]

    log_lines = []
    if room.log_text:
        recent_log = room.log_text[-3000:]
        log_lines = [line for line in recent_log.split('\n') if line]

    return render(request, 'tv/program_room_dashboard.html', {
        'room': room,
        'current_show': current_show,
        'upcoming_shows': upcoming_shows,
        'cache_status': cache_status,
        'recent_processes': recent_processes,
        'log_lines': log_lines,
        'page': 'admin',
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_start_stream(request):
    """
    Startet Stream über python_streamer.py - KORRIGIERTE VERSION
    
    FIXES:
    - Korrekte RTMP URL Konstruktion
    - Bessere Key-Validierung
    - Detailliertes Logging
    - Fehlerbehandlung verbessert
    """
    from python_streamer import get_stream_controller, reset_stream_controller
    from tv.models import ProgramRoom
    
    room, _ = ProgramRoom.objects.get_or_create(pk=1)
    
    # Stream-Keys aus POST holen
    youtube_key = request.POST.get('youtube_key', '').strip()
    twitch_key = request.POST.get('twitch_key', '').strip()
    
    # Keys speichern wenn vorhanden
    if youtube_key:
        room.youtube_stream_key = youtube_key
        os.environ['YOUTUBE_STREAM_KEY'] = youtube_key
        room.append_log(f"🔑 YouTube Key gesetzt ({len(youtube_key)} chars)")
    if twitch_key:
        room.twitch_stream_key = twitch_key
        os.environ['TWITCH_STREAM_KEY'] = twitch_key
        room.append_log(f"🔑 Twitch Key gesetzt ({len(twitch_key)} chars)")
    
    # RTMP URLs sicherstellen
    if not room.youtube_rtmp_url:
        room.youtube_rtmp_url = 'rtmp://a.rtmp.youtube.com/live2'
    if not room.twitch_rtmp_url:
        room.twitch_rtmp_url = 'rtmp://live.twitch.tv/app'
    
    room.save()
    
    # Validierung: Mindestens ein Key muss vorhanden sein
    has_youtube = bool(youtube_key or room.youtube_stream_key)
    has_twitch = bool(twitch_key or room.twitch_stream_key)
    
    if not has_youtube and not has_twitch:
        room.append_log("❌ Keine Stream-Keys konfiguriert!")
        return JsonResponse({
            'success': False,
            'error': 'Bitte mindestens einen Stream-Key eingeben!'
        }, status=400)
    
    try:
        # Setze Streaming-Flags
        if has_youtube:
            room.is_streaming_youtube = True
            room.append_log(f"📺 YouTube aktiviert: {room.youtube_rtmp_url}")
        if has_twitch:
            room.is_streaming_twitch = True
            room.append_log(f"🎮 Twitch aktiviert: {room.twitch_rtmp_url}")
        
        room.save()
        
        # Alte Controller-Instanz zurücksetzen
        reset_stream_controller()
        
        room.append_log("🎬 Starte Python-Streamer v7.2...")
        
        # Hole/Erstelle Python-Stream-Controller
        controller = get_stream_controller(program_room=room)
        
        # Starte Stream
        success = controller.start()
        
        if not success:
            room.is_streaming_youtube = False
            room.is_streaming_twitch = False
            room.save()
            room.append_log("❌ Stream-Start fehlgeschlagen - prüfe Log!")
            return JsonResponse({
                'success': False,
                'error': 'Stream-Start fehlgeschlagen - prüfe rsl_stream.log'
            }, status=500)
        
        # Erfolg!
        platforms = []
        if room.is_streaming_youtube:
            platforms.append('YouTube')
        if room.is_streaming_twitch:
            platforms.append('Twitch')
        
        platform_str = ' & '.join(platforms)
        room.append_log(f"✅ Stream läuft auf: {platform_str}")
        
        return JsonResponse({
            'success': True,
            'message': f'Stream gestartet auf {platform_str}!',
            'platforms': platforms
        })
        
    except Exception as e:
        room.is_streaming_youtube = False
        room.is_streaming_twitch = False
        room.save()
        room.append_log(f"❌ FEHLER: {str(e)}")
        
        import traceback
        room.append_log(f"Stack Trace: {traceback.format_exc()[:500]}")
        
        return JsonResponse({
            'success': False,
            'error': f'Fehler: {str(e)}'
        }, status=500)
 
 
@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_stop_stream(request):
    """Stoppt den laufenden Python-Stream"""
    from python_streamer import get_stream_controller, reset_stream_controller
    from tv.models import ProgramRoom
    
    room, _ = ProgramRoom.objects.get_or_create(pk=1)
 
    try:
        # Stoppe Python-Stream
        controller = get_stream_controller()
        if controller and controller.is_running:
            controller.stop()
            room.append_log("⏹ Python-Stream gestoppt")
        
        # Reset Controller
        reset_stream_controller()
        
    except Exception as e:
        room.append_log(f"⏹ Stream-Stop-Fehler: {e}")
 
    room.is_streaming_youtube = False
    room.is_streaming_twitch = False
    room.ffmpeg_pid = None
    room.ad_break_active = False
    room.save()
 
    return JsonResponse({'status': 'success', 'message': 'Stream gestoppt'})
 
 
@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_save_keys_api(request):
    """Speichert Stream-Keys und RTMP-URLs"""
    from tv.models import ProgramRoom
    
    data = json.loads(request.body) if request.body else request.POST.dict()
    room, _ = ProgramRoom.objects.get_or_create(id=1)
    
    if 'youtube_key' in data:
        room.youtube_stream_key = data['youtube_key']
        room.append_log(f"💾 YouTube Key gespeichert")
    if 'youtube_rtmp' in data:
        room.youtube_rtmp_url = data['youtube_rtmp']
    if 'twitch_key' in data:
        room.twitch_stream_key = data['twitch_key']
        room.append_log(f"💾 Twitch Key gespeichert")
    if 'twitch_rtmp' in data:
        room.twitch_rtmp_url = data['twitch_rtmp']
    
    room.save()
    return JsonResponse({'success': True, 'message': 'Keys gespeichert'})
 

@staff_member_required
@require_GET
def program_get_log(request):
    """Gibt aktuellen ProgramRoom Log zurück"""
    room, _ = ProgramRoom.objects.get_or_create(pk=1)
    
    return JsonResponse({
        'log': room.log_text or '',
        'is_streaming': room.is_streaming_youtube or room.is_streaming_twitch
    })


@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_trigger_ad(request):
    """Löst eine Werbepause aus (max 600s)"""
    room, _ = ProgramRoom.objects.get_or_create(pk=1)

    if room.ad_break_active:
        return JsonResponse({'status': 'error', 'message': 'Werbepause bereits aktiv'}, status=400)

    now = timezone.now()
    room.ad_break_active = True
    room.ad_break_started_at = now
    room.ad_break_ends_at = now + timedelta(seconds=600)
    room.save(update_fields=['ad_break_active', 'ad_break_started_at', 'ad_break_ends_at', 'updated_at'])
    room.append_log("🎯 Manuelle Werbepause ausgelöst (max 600s)")

    return JsonResponse({'status': 'success', 'message': 'Werbepause gestartet', 'ends_at': room.ad_break_ends_at.isoformat()})


@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_save_keys(request):
    """Speichert Stream-Keys und RTMP-URLs"""
    room, _ = ProgramRoom.objects.get_or_create(pk=1)
    room.youtube_stream_key = request.POST.get('youtube_stream_key', room.youtube_stream_key)
    room.twitch_stream_key = request.POST.get('twitch_stream_key', room.twitch_stream_key)
    room.youtube_rtmp_url = request.POST.get('youtube_rtmp_url', room.youtube_rtmp_url) or 'rtmp://a.rtmp.youtube.com/live2'
    room.twitch_rtmp_url = request.POST.get('twitch_rtmp_url', room.twitch_rtmp_url) or 'rtmp://live.twitch.tv/app'
    room.buffer_ahead_minutes = int(request.POST.get('buffer_ahead_minutes', room.buffer_ahead_minutes) or 5)
    room.save()
    room.append_log("💾 Stream-Keys gespeichert")
    return JsonResponse({'status': 'success', 'message': 'Stream-Keys gespeichert'})

@require_GET
def program_room_status_api(request):
    """
    Live-Status-API für das Dashboard
    GET /api/program/status/
    """
    from tv.models import ProgramRoom, Schedule
    
    try:
        room = ProgramRoom.objects.first()
        
        if not room:
            return JsonResponse({
                'is_streaming': False,
                'youtube_live': False,
                'twitch_live': False,
                'current_show': None,
                'next_shows': [],
                'stream_keys_set': False
            })
        
        # Stream-Status
        youtube_live = room.is_streaming_youtube and bool(room.youtube_stream_key)
        twitch_live = room.is_streaming_twitch and bool(room.twitch_stream_key)
        
        # FFmpeg läuft? (nur als Info)
        import subprocess
        ffmpeg_running = False
        try:
            result = subprocess.run(['pgrep', '-f', 'python.*streamer'], 
                                   capture_output=True, text=True, timeout=2)
            ffmpeg_running = bool(result.stdout.strip())
        except:
            pass
        
        # Aktuelle Sendung
        now = timezone.now()
        current = Schedule.objects.filter(
            start_time__lte=now, end_time__gte=now, is_active=True
        ).first()
        
        current_show = None
        if current:
            current_show = {
                'title': current.title,
                'start_time': current.start_time.isoformat(),
                'end_time': current.end_time.isoformat()
            }
        
        # Nächste Sendungen (6h)
        next_end = now + timezone.timedelta(hours=6)
        next_shows = []
        for s in Schedule.objects.filter(
            start_time__gte=now, start_time__lte=next_end, is_active=True
        ).order_by('start_time')[:10]:
            next_shows.append({
                'title': s.title,
                'start_time': s.start_time.isoformat(),
                'end_time': s.end_time.isoformat()
            })
        
        # Log extrahieren
        log_lines = []
        if room.log_text:
            log_lines = [line for line in room.log_text.split('\n') if line][-20:]
        
        return JsonResponse({
            'is_streaming_youtube': room.is_streaming_youtube,
            'is_streaming_twitch': room.is_streaming_twitch,
            'is_streaming': ffmpeg_running or room.is_streaming_youtube or room.is_streaming_twitch,
            'ad_break_active': room.ad_break_active,
            'ad_break_ends_at': room.ad_break_ends_at.isoformat() if room.ad_break_ends_at else None,
            'youtube_live': youtube_live,
            'twitch_live': twitch_live,
            'current_show': current_show,
            'next_shows': next_shows,
            'stream_keys_set': bool(room.youtube_stream_key or room.twitch_stream_key),
            'ffmpeg_running': ffmpeg_running,
            'log_tail': log_lines,
            'video_position_seconds': room.video_position_seconds,
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'is_streaming': False,
            'youtube_live': False,
            'twitch_live': False,
            'current_show': None,
            'next_shows': [],
            'stream_keys_set': False
        }, status=500)


@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_room_download_video(request):
    """Startet manuell den Download/Cache eines Videos"""
    video_id = request.POST.get('video_id')
    if not video_id:
        return JsonResponse({'status': 'error', 'message': 'video_id fehlt'}, status=400)

    video = get_object_or_404(Video, pk=video_id)

    cache, created = VideoCache.objects.get_or_create(video=video)
    if cache.status == 'ready' and cache.is_ready():
        return JsonResponse({'status': 'already_ready', 'message': 'Video bereits im Cache'})

    cache.status = 'downloading'
    cache.progress_percent = 0
    cache.error_message = ''
    cache.save()

    def do_download():
        _download_video_to_cache(video, cache)

    t = threading.Thread(target=do_download, daemon=True)
    t.start()

    return JsonResponse({'status': 'started', 'message': f'Download von "{video.title}" gestartet'})


# ══════════════════════════════════════════════════════════════════════════════
# INTERNE STREAM-LOGIK (Hintergrund-Prozesse)
# ══════════════════════════════════════════════════════════════════════════════

def _download_video_to_cache(video, cache):
    """Lädt ein Video herunter und speichert es lokal."""
    import subprocess, os

    cache_dir = '/tmp/rsl_video_cache'
    os.makedirs(cache_dir, exist_ok=True)

    safe_name = f"video_{video.id}.mp4"
    out_path = os.path.join(cache_dir, safe_name)

    try:
        if video.source_type == 'youtube':
            cmd = [
                'yt-dlp',
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                '--merge-output-format', 'mp4',
                '-o', out_path,
                '--no-playlist',
                '--newline',
                video.source_url,
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                if '[download]' in line and '%' in line:
                    try:
                        pct = float(line.split('%')[0].split()[-1])
                        cache.progress_percent = int(pct)
                        cache.save(update_fields=['progress_percent'])
                    except Exception:
                        pass
            proc.wait()
            if proc.returncode != 0:
                raise Exception(f"yt-dlp Fehler (exit {proc.returncode})")

        elif video.source_type in ('gdrive', 'dropbox', 'direct'):
            import urllib.request
            url = video.get_stream_url()

            def progress_hook(count, block_size, total_size):
                if total_size > 0:
                    pct = int(count * block_size * 100 / total_size)
                    cache.progress_percent = min(pct, 99)
                    cache.save(update_fields=['progress_percent'])

            urllib.request.urlretrieve(url, out_path, reporthook=progress_hook)

        else:
            raise Exception(f"Quelle '{video.source_type}' nicht zum Download unterstützt")

        try:
            r = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', out_path],
                capture_output=True, text=True, timeout=10
            )
            cache.duration_seconds = int(float(r.stdout.strip()))
        except Exception:
            pass

        cache.file_size_mb = round(os.path.getsize(out_path) / 1024 / 1024, 1)
        cache.local_path = out_path
        cache.status = 'ready'
        cache.progress_percent = 100
        cache.downloaded_at = timezone.now()
        cache.save()

    except Exception as e:
        cache.status = 'error'
        cache.error_message = str(e)
        cache.save()


def _run_program_stream(room, targets):
    """Haupt-Stream-Loop für den Programm-Regieraum."""
    import subprocess, time

    room.append_log(f"🚀 Stream-Loop gestartet | Ziele: {[p for p, _ in targets]}")

    def build_ffmpeg_cmd(input_source, seek=0, duration=None, is_image=False):
        cmd = ['ffmpeg', '-loglevel', 'warning', '-stats']

        if is_image:
            cmd += ['-loop', '1', '-framerate', '25', '-i', input_source]
            cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo']
        else:
            if seek > 0:
                cmd += ['-ss', str(int(seek))]
            cmd += ['-re', '-i', input_source]

        if duration:
            cmd += ['-t', str(int(duration))]

        cmd += [
            '-c:v', 'libx264', '-preset', 'veryfast',
            '-maxrate', '3500k', '-bufsize', '7000k',
            '-pix_fmt', 'yuv420p', '-g', '60', '-r', '30',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
        ]

        if is_image:
            cmd += ['-map', '0:v', '-map', '1:a']
        else:
            cmd += ['-map', '0:v?', '--map', '0:a?']

        if len(targets) == 1:
            cmd += ['-f', 'flv', targets[0][1]]
        else:
            tee_parts = '|'.join(f'[f=flv]{url}' for _, url in targets)
            cmd += ['-f', 'tee', tee_parts]

        return cmd

    def play_content(source_path, seek=0, duration=None, is_image=False, label=''):
        room.append_log(f"▶ {label}")
        cmd = build_ffmpeg_cmd(source_path, seek=seek, duration=duration, is_image=is_image)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            room.ffmpeg_pid = proc.pid
            room.save(update_fields=['ffmpeg_pid', 'updated_at'])
            return proc
        except FileNotFoundError:
            room.append_log("❌ FFmpeg nicht gefunden!")
            return None

    def get_ad_videos():
        now = timezone.now()
        spots = list(AdVideo.objects.filter(
            ad_type='spot', is_active=True
        ).filter(
            DQ(advertisement__isnull=True) |
            DQ(
                advertisement__status='active',
                advertisement__paid=True,
                advertisement__start_date__lte=now.date(),
                advertisement__end_date__gte=now.date(),
            )
        ).order_by('?')[:5])
        return spots

    iteration = 0
    while True:
        try:
            iteration += 1
            room.refresh_from_db()

            if not room.is_streaming_youtube and not room.is_streaming_twitch:
                room.append_log("⏹ Stream-Loop beendet (kein aktives Ziel)")
                break

            now = timezone.now()

            # WERBEPAUSE
            if room.ad_break_active:
                room.append_log("🎯 Werbepause läuft")
                ads = get_ad_videos()
                if ads:
                    for ad in ads:
                        room.refresh_from_db()
                        if not room.ad_break_active:
                            break
                        if room.ad_break_ends_at and timezone.now() >= room.ad_break_ends_at:
                            break
                        proc = play_content(
                            ad.video_url, duration=ad.duration,
                            label=f"Werbung: {ad.title} ({ad.duration}s)"
                        )
                        if proc:
                            remaining = int((room.ad_break_ends_at - timezone.now()).total_seconds()) if room.ad_break_ends_at else ad.duration
                            try:
                                proc.wait(timeout=min(ad.duration + 5, max(remaining, 0) + 5))
                            except subprocess.TimeoutExpired:
                                proc.terminate()
                else:
                    from .models import StandbyImage
                    sb = StandbyImage.objects.filter(is_active=True).first()
                    if sb and sb.image:
                        remaining = int((room.ad_break_ends_at - timezone.now()).total_seconds()) if room.ad_break_ends_at else 30
                        proc = play_content(sb.image.path, is_image=True, duration=max(remaining, 5), label="Werbepause (Pausenbild)")
                        if proc:
                            try:
                                proc.wait(timeout=max(remaining, 5) + 5)
                            except subprocess.TimeoutExpired:
                                proc.terminate()
                    else:
                        time.sleep(5)

                room.refresh_from_db()
                room.ad_break_active = False
                room.save(update_fields=['ad_break_active', 'updated_at'])
                room.append_log("✅ Werbepause beendet – Video wird fortgesetzt")
                continue

            # SENDEPLAN-VIDEO
            current_show = Schedule.objects.filter(
                start_time__lte=now, end_time__gte=now, is_active=True
            ).select_related('video').first()

            if current_show and current_show.video:
                video = current_show.video
                elapsed = int((now - current_show.start_time).total_seconds())

                resume_at = max(elapsed, room.video_position_seconds)

                remaining_duration = int((current_show.end_time - now).total_seconds())
                if remaining_duration <= 0:
                    time.sleep(2)
                    continue

                cache = getattr(video, 'cache', None)
                if cache and cache.is_ready():
                    source = cache.local_path
                    room.append_log(f"📁 Lokal: {video.title} ab {resume_at}s")
                elif video.source_type == 'youtube':
                    try:
                        r = subprocess.run(
                            ['yt-dlp', '-g', '-f', 'best[ext=mp4]/best', video.source_url],
                            capture_output=True, text=True, timeout=15
                        )
                        source = r.stdout.strip().split('\n')[0] if r.returncode == 0 else None
                    except Exception:
                        source = None

                    if not source:
                        room.append_log(f"⚠ YouTube-URL konnte nicht aufgelöst werden: {video.title}")
                        time.sleep(10)
                        continue
                    room.append_log(f"🌐 YouTube-Stream: {video.title} ab {resume_at}s")
                else:
                    source = video.get_stream_url()
                    room.append_log(f"🌐 Stream: {video.title} ab {resume_at}s")

                next_ad_break = current_show.ad_breaks.filter(
                    time_offset_seconds__gt=resume_at,
                    played=False
                ).order_by('time_offset_seconds').first()

                if next_ad_break:
                    play_until = next_ad_break.time_offset_seconds - resume_at
                    proc = play_content(
                        source, seek=resume_at, duration=play_until,
                        label=f"▶ {current_show.title} ({resume_at}s → {next_ad_break.time_offset_seconds}s)"
                    )
                    if proc:
                        proc.wait()

                    room.video_position_seconds = next_ad_break.time_offset_seconds
                    room.ad_break_active = True
                    room.ad_break_started_at = timezone.now()
                    room.ad_break_ends_at = timezone.now() + timedelta(seconds=600)
                    room.save(update_fields=['video_position_seconds', 'ad_break_active',
                                             'ad_break_started_at', 'ad_break_ends_at', 'updated_at'])
                    next_ad_break.played = True
                    next_ad_break.played_at = timezone.now()
                    next_ad_break.save()
                    room.append_log(f"🎯 Werbepause nach {next_ad_break.time_offset_seconds}s gestartet")

                else:
                    proc = play_content(
                        source, seek=resume_at, duration=remaining_duration,
                        label=f"▶ {current_show.title} (bis Ende)"
                    )
                    room.video_position_seconds = 0
                    room.save(update_fields=['video_position_seconds', 'updated_at'])
                    if proc:
                        proc.wait()

            else:
                # PAUSENBILD
                from .models import StandbyImage
                sb = StandbyImage.objects.filter(is_active=True).first()

                next_show = Schedule.objects.filter(
                    start_time__gte=now, is_active=True, video__isnull=False
                ).select_related('video').order_by('start_time').first()

                if next_show and next_show.video:
                    _trigger_buffer_download(next_show, room)

                if sb and sb.image:
                    proc = play_content(sb.image.path, is_image=True, duration=30, label="📺 Pausenbild")
                    if proc:
                        try:
                            proc.wait(timeout=35)
                        except subprocess.TimeoutExpired:
                            proc.terminate()
                else:
                    time.sleep(10)

        except KeyboardInterrupt:
            break
        except Exception as e:
            room.append_log(f"❌ Fehler in Stream-Loop: {e}")
            time.sleep(5)

    room.is_streaming_youtube = False
    room.is_streaming_twitch = False
    room.ffmpeg_pid = None
    room.save()
    room.append_log("🏁 Stream-Loop beendet")


def _trigger_buffer_download(next_show, room):
    """Startet den Vorab-Download wenn die Sendung in < buffer_ahead_minutes beginnt."""
    video = next_show.video
    if not video or video.source_type not in ('youtube', 'gdrive', 'dropbox'):
        return

    cache, created = VideoCache.objects.get_or_create(video=video)
    if cache.status in ('ready', 'downloading'):
        return

    now = timezone.now()
    time_until_start = (next_show.start_time - now).total_seconds()

    estimated_download_time = video.duration * 2.5 if video.duration > 0 else 300

    trigger_threshold = estimated_download_time + (room.buffer_ahead_minutes * 60)

    if time_until_start <= trigger_threshold:
        cache.status = 'downloading'
        cache.save(update_fields=['status'])
        room.append_log(f"⬇ Starte Vorab-Download: {video.title} ({time_until_start/60:.0f} min bis Sendebeginn)")

        def do_download():
            _download_video_to_cache(video, cache)

        t = threading.Thread(target=do_download, daemon=True)
        t.start()


# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTIFIZIERUNG (Login/Registrierung)
# ══════════════════════════════════════════════════════════════════════════════

from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

def login_view(request):
    """Login View"""
    if request.user.is_authenticated:
        return redirect('program_room_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or 'program_room_dashboard'
            messages.success(request, f'Willkommen zurück, {user.username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Ungültige Anmeldedaten.')
    
    return render(request, 'registration/login.html')


def register_view(request):
    """Registrierungs View"""
    if request.user.is_authenticated:
        return redirect('program_room_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        errors = []
        
        # Validierung
        if not username or len(username) < 3:
            errors.append('Benutzername muss mindestens 3 Zeichen lang sein.')
        
        if User.objects.filter(username=username).exists():
            errors.append('Dieser Benutzername ist bereits vergeben.')
        
        if not email or '@' not in email:
            errors.append('Bitte gib eine gültige E-Mail Adresse ein.')
        
        if User.objects.filter(email=email).exists():
            errors.append('Diese E-Mail Adresse ist bereits registriert.')
        
        if not password1 or len(password1) < 8:
            errors.append('Passwort muss mindestens 8 Zeichen lang sein.')
        
        if password1 != password2:
            errors.append('Die Passwörter stimmen nicht überein.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # User erstellen
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            login(request, user)
            messages.success(request, f'Account erfolgreich erstellt! Willkommen, {user.username}!')
            return redirect('program_room_dashboard')
    
    return render(request, 'registration/register.html')


def logout_view(request):
    """Logout View"""
    logout(request)
    messages.success(request, 'Du wurdest erfolgreich abgemeldet.')
    return redirect('home')


# ══════════════════════════════════════════════════════════════════════════════
# LIVE STUDIO (OBS-Style Interface)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def live_studio(request):
    """Haupt-Live-Studio Interface"""
    return render(request, 'tv/live_studio.html')


@login_required
def api_cameras_list(request):
    """Liste aller verfügbaren Kameras"""
    cameras = Camera.objects.filter(is_active=True)
    data = []
    
    for camera in cameras:
        data.append({
            'id': camera.id,
            'name': camera.name,
            'source_type': camera.source_type,
            'stream_url': camera.stream_url if camera.source_type == 'url' else None,
            'device_index': camera.device_index if camera.source_type == 'webcam' else None,
            'is_active': camera.is_active,
        })
    
    return JsonResponse(data, safe=False)


@login_required
def api_scenes_list(request):
    """Liste aller Szenen mit ihren Quellen"""
    scenes = Scene.objects.all()
    data = []
    
    for scene in scenes:
        sources = []
        for source in scene.sources.all():
            sources.append({
                'id': source.id,
                'name': source.name,
                'source_type': source.source_type,
                'visible': source.visible,
                'x': source.x,
                'y': source.y,
                'width': source.width,
                'height': source.height,
            })
        
        data.append({
            'id': scene.id,
            'name': scene.name,
            'description': scene.description,
            'is_active': scene.is_active,
            'sources': sources,
        })
    
    return JsonResponse(data, safe=False)


@login_required
def api_rundown_active(request):
    """Aktiver Rundown mit allen Segmenten"""
    try:
        # Hole den aktuellsten aktiven Rundown
        rundown = ShowRundown.objects.filter(is_active=True).order_by('-show_date').first()
        
        if not rundown:
            return JsonResponse({'segments': []})
        
        segments = []
        for segment in rundown.segments.all().order_by('order'):
            scene_data = None
            if segment.scene:
                scene_data = {
                    'id': segment.scene.id,
                    'name': segment.scene.name,
                }
            
            segments.append({
                'id': segment.id,
                'title': segment.title,
                'segment_type': segment.segment_type,
                'description': segment.description,
                'planned_duration': segment.planned_duration,
                'actual_duration': segment.actual_duration,
                'video_url': segment.video_url,
                'scene': scene_data,
                'is_ready': segment.is_ready,
                'was_played': segment.was_played,
                'played_at': segment.played_at.isoformat() if segment.played_at else None,
                'script': segment.script,
                'notes': segment.notes,
            })
        
        return JsonResponse({
            'id': rundown.id,
            'title': rundown.title,
            'show_date': rundown.show_date.isoformat(),
            'is_live': rundown.is_live,
            'segments': segments,
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_get_ad_break(request):
    """Hole einen Werbeblock für die Ausstrahlung"""
    try:
        # Standardmäßig 3 Minuten Werbung
        max_duration = 180
        
        # Hole Template falls vorhanden
        template = AdBreakTemplate.objects.filter(is_active=True).first()
        
        if template:
            ads = template.build_block()
        else:
            # Fallback: Zufällige aktive Werbespots
            ads = list(AdVideo.objects.filter(
                ad_type='spot',
                is_active=True
            ).order_by('?')[:5])
        
        # Konvertiere zu JSON
        result = []
        for ad in ads:
            result.append({
                'id': ad.id,
                'title': ad.title,
                'video_url': ad.video_file.url if ad.video_file else ad.video_url,
                'duration': ad.duration,
                'ad_type': ad.ad_type,
            })
        
        return JsonResponse(result, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_stream_key(request, platform):
    """Hole Stream Key für Platform (YouTube/Twitch)"""
    try:
        # Hole DirectorRoom des Users (oder Standard)
        room = DirectorRoom.objects.filter(is_active=True).first()
        
        if not room:
            return JsonResponse({'error': 'Kein aktiver Regieraum gefunden'}, status=404)
        
        if platform == 'youtube':
            key = room.youtube_stream_key
        elif platform == 'twitch':
            key = room.twitch_stream_key
        else:
            return JsonResponse({'error': 'Unbekannte Platform'}, status=400)
        
        return JsonResponse({
            'platform': platform,
            'key': key if key else None,
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_stream_start(request, platform):
    """Starte Streaming zu Platform"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        # Hole DirectorRoom
        room = DirectorRoom.objects.filter(is_active=True).first()
        
        if not room:
            return JsonResponse({'error': 'Kein aktiver Regieraum'}, status=404)
        
        # Speichere WebRTC Offer (SDP)
        # In einer echten Implementierung würde hier die WebRTC-Signalisierung erfolgen
        # und eine Verbindung zu einem Media-Server hergestellt werden
        
        # Aktualisiere Status
        if platform == 'youtube':
            room.is_streaming_youtube = True
        elif platform == 'twitch':
            room.is_streaming_twitch = True
        
        room.save()
        
        # Erstelle dummy WebRTC Answer
        # In Produktion würde hier ein echter Media-Server antworten
        answer = {
            'type': 'answer',
            'sdp': 'v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n'
        }
        
        return JsonResponse(answer)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_stream_stop(request, platform):
    """Stoppe Streaming zu Platform"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        room = DirectorRoom.objects.filter(is_active=True).first()
        
        if not room:
            return JsonResponse({'error': 'Kein aktiver Regieraum'}, status=404)
        
        # Aktualisiere Status
        if platform == 'youtube':
            room.is_streaming_youtube = False
        elif platform == 'twitch':
            room.is_streaming_twitch = False
        
        room.save()
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Füge diese Funktionen zu tv/views.py hinzu

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json

@login_required
def pause_screen_manager(request):
    """Pausenbild-Verwaltung"""
    pause_screens = PauseScreen.objects.all()
    return render(request, 'tv/pause_screen_manager.html', {
        'pause_screens': pause_screens
    })


@login_required
def api_pause_screen_activate(request):
    """Aktiviert ein Pausenbild"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        pause_screen_id = data.get('pause_screen_id')
        
        if pause_screen_id == 'default':
            # Deaktiviere alle
            PauseScreen.objects.all().update(is_active=False)
            return JsonResponse({'success': True, 'active': 'default'})
        
        pause_screen = PauseScreen.objects.get(id=pause_screen_id)
        pause_screen.activate()
        
        return JsonResponse({
            'success': True,
            'active': pause_screen.id,
            'title': pause_screen.title
        })
    
    except PauseScreen.DoesNotExist:
        return JsonResponse({'error': 'Pausenbild nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_pause_screen_create(request):
    """Erstellt ein neues Pausenbild"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        title = request.POST.get('title')
        bg_type = request.POST.get('bg_type')
        color1 = request.POST.get('color1', '#e63946')
        color2 = request.POST.get('color2', '#c1121f')
        main_text = request.POST.get('main_text', 'Kurze Pause')
        sub_text = request.POST.get('sub_text', 'Wir sind gleich zurück')
        show_logo = request.POST.get('show_logo', 'yes') == 'yes'
        animation = request.POST.get('animation', 'none')
        
        pause_screen = PauseScreen.objects.create(
            title=title,
            background_type=bg_type,
            color_primary=color1,
            color_secondary=color2,
            main_text=main_text,
            sub_text=sub_text,
            show_logo=show_logo,
            animation=animation,
            created_by=request.user
        )
        
        # Bild hochladen falls vorhanden
        if 'bg_image' in request.FILES:
            pause_screen.background_image = request.FILES['bg_image']
            pause_screen.save()
        
        return JsonResponse({
            'success': True,
            'id': pause_screen.id,
            'title': pause_screen.title
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_pause_screen_get_active(request):
    """Gibt das aktive Pausenbild zurück"""
    try:
        pause_screen = PauseScreen.objects.filter(is_active=True).first()
        
        if not pause_screen:
            # Rückgabe Standard
            return JsonResponse({
                'type': 'default',
                'main_text': 'Kurze Pause',
                'sub_text': 'Wir sind gleich zurück',
                'show_logo': True,
                'background': 'linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%)'
            })
        
        return JsonResponse({
            'id': pause_screen.id,
            'type': 'custom',
            'title': pause_screen.title,
            'main_text': pause_screen.main_text,
            'sub_text': pause_screen.sub_text,
            'show_logo': pause_screen.show_logo,
            'background': pause_screen.get_css_background(),
            'animation': pause_screen.animation,
            'logo_url': pause_screen.custom_logo.url if pause_screen.custom_logo else None
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_overlays_list(request):
    """Liste aller aktiven Overlays"""
    try:
        overlays = StreamOverlay.objects.filter(is_active=True)
        data = []
        
        for overlay in overlays:
            data.append({
                'id': overlay.id,
                'name': overlay.name,
                'type': overlay.overlay_type,
                'position': overlay.position,
                'text': overlay.text_content,
                'background_color': overlay.background_color,
                'text_color': overlay.text_color,
                'font_size': overlay.font_size,
                'duration': overlay.duration,
                'animation_in': overlay.animation_in,
                'animation_out': overlay.animation_out,
            })
        
        return JsonResponse(data, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_overlay_show(request):
    """Zeigt ein Overlay an"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        overlay_id = data.get('overlay_id')
        
        overlay = StreamOverlay.objects.get(id=overlay_id)
        
        return JsonResponse({
            'success': True,
            'overlay': {
                'id': overlay.id,
                'name': overlay.name,
                'type': overlay.overlay_type,
                'position': overlay.position,
                'text': overlay.text_content,
                'background_color': overlay.background_color,
                'text_color': overlay.text_color,
                'font_size': overlay.font_size,
                'duration': overlay.duration,
                'animation_in': overlay.animation_in,
                'animation_out': overlay.animation_out,
            }
        })
    
    except StreamOverlay.DoesNotExist:
        return JsonResponse({'error': 'Overlay nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_cutouts_list(request):
    """Liste aller Cut-Out Grafiken"""
    try:
        category = request.GET.get('category', None)
        
        cutouts = CutOutGraphic.objects.filter(is_active=True)
        if category:
            cutouts = cutouts.filter(category=category)
        
        data = []
        for cutout in cutouts:
            data.append({
                'id': cutout.id,
                'name': cutout.name,
                'category': cutout.category,
                'image_url': cutout.image.url,
                'default_x': cutout.default_x,
                'default_y': cutout.default_y,
                'default_width': cutout.default_width,
                'default_height': cutout.default_height,
                'hotkey': cutout.hotkey,
                'can_animate': cutout.can_animate,
            })
        
        return JsonResponse(data, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_cutout_use(request):
    """Verwendet eine Cut-Out Grafik"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        cutout_id = data.get('cutout_id')
        
        cutout = CutOutGraphic.objects.get(id=cutout_id)
        cutout.use()
        
        return JsonResponse({
            'success': True,
            'cutout': {
                'id': cutout.id,
                'name': cutout.name,
                'image_url': cutout.image.url,
                'x': cutout.default_x,
                'y': cutout.default_y,
                'width': cutout.default_width,
                'height': cutout.default_height,
            }
        })
    
    except CutOutGraphic.DoesNotExist:
        return JsonResponse({'error': 'Cut-Out nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_stream_presets_list(request):
    """Liste aller Stream-Presets"""
    try:
        presets = StreamPreset.objects.all()
        data = []
        
        for preset in presets:
            data.append({
                'id': preset.id,
                'name': preset.name,
                'description': preset.description,
                'resolution': preset.resolution,
                'fps': preset.fps,
                'bitrate': preset.bitrate,
                'audio_bitrate': preset.audio_bitrate,
                'is_active': preset.is_active,
                'scene_id': preset.default_scene.id if preset.default_scene else None,
            })
        
        return JsonResponse(data, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_preset_activate(request):
    """Aktiviert ein Stream-Preset"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        preset_id = data.get('preset_id')
        
        preset = StreamPreset.objects.get(id=preset_id)
        preset.activate()
        
        return JsonResponse({
            'success': True,
            'preset': {
                'id': preset.id,
                'name': preset.name,
                'resolution': preset.resolution,
                'fps': preset.fps,
                'bitrate': preset.bitrate,
            }
        })
    
    except StreamPreset.DoesNotExist:
        return JsonResponse({'error': 'Preset nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_rundown_segment_delete(request, segment_id):
    """Löscht ein Rundown-Segment"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        segment = ContentSegment.objects.get(id=segment_id)
        rundown = segment.rundown
        segment.delete()
        
        # Rundown-Dauer neu berechnen
        rundown.calculate_total_duration()
        
        return JsonResponse({'success': True})
    
    except ContentSegment.DoesNotExist:
        return JsonResponse({'error': 'Segment nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# TV-DISPLAY APIs (Werbepausen & Programmsteuerung)
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def api_ad_break_status(request):
    """
    API: Werbepausen-Status
    GET /api/ad-break-status/
    """
    from tv.models import LiveAdBreak
    
    try:
        active_break = LiveAdBreak.objects.filter(
            is_active=True,
            ended_at__isnull=True
        ).first()
        
        if active_break:
            now = timezone.now()
            elapsed = (now - active_break.started_at).total_seconds()
            remaining = max(0, active_break.max_duration - elapsed)
            
            return JsonResponse({
                'is_active': True,
                'remaining_seconds': int(remaining),
                'started_at': active_break.started_at.isoformat()
            })
        
        return JsonResponse({'is_active': False})
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'is_active': False
        }, status=500)
 
 
@csrf_exempt
@require_POST
def api_start_ad_break(request):
    """
    API: Werbepause starten
    POST /api/ad-break/start/
    """
    from tv.models import LiveAdBreak
    
    try:
        try:
            data = json.loads(request.body)
        except:
            data = {}
        
        duration = data.get('duration', 120)
        
        ad_break = LiveAdBreak.objects.create(
            max_duration=int(duration),
            is_active=True,
            started_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'ad_break_id': ad_break.id,
            'duration': duration
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
 
 
@csrf_exempt
@require_POST
def api_end_ad_break(request):
    """
    API: Werbepause beenden
    POST /api/ad-break/end/
    """
    from tv.models import LiveAdBreak
    
    try:
        active_break = LiveAdBreak.objects.filter(
            is_active=True,
            ended_at__isnull=True
        ).first()
        
        if active_break:
            active_break.is_active = False
            active_break.ended_at = timezone.now()
            active_break.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Werbepause beendet'
            })
        
        return JsonResponse({
            'success': False,
            'message': 'Keine aktive Werbepause'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
 
 
# ============================================================================
# DASHBOARD VIEW
# ============================================================================
 
@login_required
@user_passes_test(is_director)
def program_room_dashboard(request):
    """Programm-Regieraum: Sendeplan-Stream steuern"""
    from tv.models import ProgramRoom, Schedule, StreamProcess
    from datetime import timedelta
    
    room, created = ProgramRoom.objects.get_or_create(pk=1)
    now = timezone.now()
 
    current_show = Schedule.objects.filter(
        start_time__lte=now, end_time__gte=now, is_active=True
    ).first()
    upcoming_shows = Schedule.objects.filter(
        start_time__gte=now, is_active=True
    ).order_by('start_time')[:10]
 
    recent_processes = StreamProcess.objects.filter(
        program_room=room
    ).order_by('-started_at')[:10]
 
    log_lines = []
    if room.log_text:
        recent_log = room.log_text[-3000:]
        log_lines = [line for line in recent_log.split('\n') if line]
 
    return render(request, 'tv/program_room_dashboard.html', {
        'room': room,
        'current_show': current_show,
        'upcoming_shows': upcoming_shows,
        'recent_processes': recent_processes,
        'log_lines': log_lines,
        'page': 'admin',
    })
 


# ============================================================================
# PROGRAMM APIs
# ============================================================================

@require_http_methods(["GET"])
def api_current_show_extended(request):
    """
    API: Aktuelles Programm (Erweiterter Alias)
    GET /api/current-show/
    
    WICHTIG: Unterscheidet sich von api_current_show() in views.py
    Dies ist ein Alias mit mehr Details für TV-Display
    
    Returns:
        {
            "current": {
                "title": "...",
                "video_url": "...",
                "start_time": "...",
                "end_time": "..."
            }
        }
    """
    try:
        from tv.models import Schedule
        
        now = timezone.now()
        
        current = Schedule.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            is_active=True
        ).select_related('video').first()
        
        if current and current.video and current.video.video_url:
            return JsonResponse({
                'current': {
                    'id': current.id,
                    'title': current.title,
                    'video_url': current.video.video_url,
                    'start_time': current.start_time.isoformat(),
                    'end_time': current.end_time.isoformat(),
                    'description': current.description or ''
                }
            })
        
        return JsonResponse({
            'current': None,
            'message': 'Kein Programm aktiv'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'current': None
        }, status=500)


"""
PROGRAM ROOM APIs - Am Ende von tv/views.py hinzufügen!
=========================================================

Diese APIs beheben den SyntaxError in der Programm-Regie.
Füge diesen Code am ENDE von tv/views.py ein.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import subprocess
import os
import signal

@csrf_exempt
@require_http_methods(["POST"])
def program_room_start_stream_api(request):
    """
    POST /api/program/start-stream/
    
    Startet python_streamer.py im Hintergrund
    """
    try:
        from tv.models import ProgramRoom
        
        data = json.loads(request.body) if request.body else {}
        platforms = data.get('platforms', 'both')
        
        room = ProgramRoom.objects.first()
        if not room:
            return JsonResponse({'success': False, 'error': 'ProgramRoom nicht konfiguriert'}, status=400)
        
        # Aktiviere Streams
        if platforms in ['both', 'youtube']:
            room.is_streaming_youtube = True
        if platforms in ['both', 'twitch']:
            room.is_streaming_twitch = True
        room.save()
        
        # Prüfe ob schon läuft
        check = subprocess.run(['pgrep', '-f', 'python.*python_streamer.py'], 
                              capture_output=True, text=True)
        if check.stdout.strip():
            return JsonResponse({'success': True, 'message': 'Stream läuft bereits', 'already_running': True})
        
        # Starte python_streamer.py
        script_path = os.path.join(os.getcwd(), 'python_streamer.py')
        if os.path.exists(script_path):
            subprocess.Popen(['python3', script_path], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            return JsonResponse({'success': True, 'message': f'Stream gestartet ({platforms})'})
        
        return JsonResponse({'success': False, 'error': 'python_streamer.py nicht gefunden'}, status=404)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def program_room_stop_stream_api(request):
    """
    POST /api/program/stop-stream/
    
    Stoppt python_streamer.py und FFmpeg
    """
    try:
        from tv.models import ProgramRoom
        
        room = ProgramRoom.objects.first()
        if room:
            room.is_streaming_youtube = False
            room.is_streaming_twitch = False
            room.save()
        
        # Stoppe python_streamer.py
        result = subprocess.run(['pgrep', '-f', 'python.*python_streamer.py'], 
                               capture_output=True, text=True)
        killed = 0
        for pid in result.stdout.strip().split('\n'):
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    killed += 1
                except:
                    pass
        
        # Stoppe FFmpeg
        subprocess.run(['pkill', '-f', 'ffmpeg.*rtmp'], timeout=5)
        
        return JsonResponse({'success': True, 'message': f'Stream gestoppt ({killed} Prozesse beendet)'})
        
    except Exception as e:
        return JsonResponse({'success': True, 'message': 'Stream-Flags deaktiviert', 'warning': str(e)})



# ============================================================================
# PROGRAMM APIs
# ============================================================================

@require_http_methods(["GET"])
def api_current_show_extended(request):
    """
    API: Aktuelles Programm (Erweiterter Alias)
    GET /api/current-show/
    """
    try:
        now = timezone.now()
        
        current = Schedule.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            is_active=True
        ).select_related('video').first()
        
        if current and current.video and current.video.video_url:
            return JsonResponse({
                'current': {
                    'id': current.id,
                    'title': current.title,
                    'video_url': current.video.video_url,
                    'start_time': current.start_time.isoformat(),
                    'end_time': current.end_time.isoformat(),
                    'description': current.description or ''
                }
            })
        
        return JsonResponse({
            'current': None,
            'message': 'Kein Programm aktiv'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'current': None
        }, status=500)


# ============================================================================
# PROGRAM ROOM APIs (korrigiert - keine doppelten Funktionen!)
# ============================================================================


@csrf_exempt
@require_http_methods(["POST"])
def program_room_start_stream_api(request):
    """
    POST /api/program/start-stream/
    """
    try:
        data = json.loads(request.body) if request.body else {}
        platforms = data.get('platforms', 'both')
        
        room = ProgramRoom.objects.first()
        if not room:
            return JsonResponse({'success': False, 'error': 'ProgramRoom nicht konfiguriert'}, status=400)
        
        # Aktiviere Streams
        if platforms in ['both', 'youtube']:
            room.is_streaming_youtube = True
        if platforms in ['both', 'twitch']:
            room.is_streaming_twitch = True
        room.save()
        
        # Starte python_streamer.py als Subprocess
        import subprocess
        import os
        
        script_path = os.path.join(os.getcwd(), 'python_streamer.py')
        
        # Prüfe ob schon läuft
        check = subprocess.run(['pgrep', '-f', 'python.*python_streamer.py'], 
                              capture_output=True, text=True)
        if check.stdout.strip():
            return JsonResponse({
                'success': True, 
                'message': 'Stream läuft bereits', 
                'already_running': True
            })
        
        if os.path.exists(script_path):
            # Starte im Hintergrund
            subprocess.Popen(
                ['python3', script_path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                start_new_session=True
            )
            room.append_log(f"🚀 Python-Streamer gestartet ({platforms})")
            return JsonResponse({
                'success': True, 
                'message': f'Stream gestartet ({platforms})'
            })
        
        return JsonResponse({
            'success': False, 
            'error': 'python_streamer.py nicht gefunden'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def program_room_stop_stream_api(request):
    """
    POST /api/program/stop-stream/
    """
    try:
        room = ProgramRoom.objects.first()
        if room:
            room.is_streaming_youtube = False
            room.is_streaming_twitch = False
            room.save()
            room.append_log("⏹ Stream gestoppt via API")
        
        # Stoppe Prozesse
        import subprocess
        import os
        import signal
        
        # Stoppe python_streamer.py
        result = subprocess.run(['pgrep', '-f', 'python.*python_streamer.py'], 
                               capture_output=True, text=True)
        killed = 0
        for pid in result.stdout.strip().split('\n'):
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    killed += 1
                except:
                    pass
        
        return JsonResponse({
            'success': True, 
            'message': f'Stream gestoppt ({killed} Prozesse beendet)'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': True, 
            'message': 'Stream-Flags deaktiviert', 
            'warning': str(e)
        })

@login_required
@user_passes_test(is_director)
@csrf_exempt
def program_clear_log(request):
    """Löscht das ProgramRoom Log"""
    room, _ = ProgramRoom.objects.get_or_create(pk=1)
    
    room.log_text = ""
    room.save(update_fields=['log_text', 'updated_at'])
    
    messages.success(request, 'Log wurde geleert.')
    return redirect('program_room_dashboard')

import subprocess
from django.http import JsonResponse

def run_ffmpeg_setup(request):
    try:
        result = subprocess.run(
            ["python", "setup_ffmpeg.py"],
            capture_output=True,
            text=True
        )

        return JsonResponse({
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })


# ══════════════════════════════════════════════════════════════════════════════
# SERIEN-SYSTEM VIEWS
# ══════════════════════════════════════════════════════════════════════════════

def series_list(request):
    """Zeigt alle aktiven Serien"""
    series = Series.objects.filter(is_active=True).order_by('-created_at')
    categories = Category.objects.all()
    
    # Filter nach Kategorie
    category_slug = request.GET.get('category')
    if category_slug:
        series = series.filter(category__slug=category_slug)
    
    # Suche
    query = request.GET.get('q')
    if query:
        series = series.filter(
            DQ(title__icontains=query) | 
            DQ(description__icontains=query) |
            DQ(tags__icontains=query)
        )
    
    return render(request, 'tv/series_list.html', {
        'series': series,
        'categories': categories,
        'current_category': category_slug,
        'search_query': query,
        'page': 'series'
    })


def series_detail(request, slug):
    """Zeigt Details einer Serie mit allen Staffeln und Episoden"""
    series = get_object_or_404(Series, slug=slug, is_active=True)
    seasons = series.seasons.filter(is_active=True).order_by('season_number').prefetch_related('episodes')
    
    # Statistiken
    total_episodes = Episode.objects.filter(season__series=series, is_active=True).count()
    total_duration = Episode.objects.filter(season__series=series, is_active=True).aggregate(
        total=Sum('duration')
    )['total'] or 0
    
    latest_episode = series.get_latest_episode()
    
    return render(request, 'tv/series_detail.html', {
        'series': series,
        'seasons': seasons,
        'total_episodes': total_episodes,
        'total_duration': total_duration,
        'latest_episode': latest_episode,
        'page': 'series'
    })


def season_detail(request, series_slug, season_number):
    """Zeigt alle Episoden einer Staffel"""
    series = get_object_or_404(Series, slug=series_slug, is_active=True)
    season = get_object_or_404(Season, series=series, season_number=season_number, is_active=True)
    episodes = season.episodes.filter(is_active=True).order_by('episode_number')
    
    # Navigation zu anderen Staffeln
    prev_season = Season.objects.filter(
        series=series, 
        season_number__lt=season_number,
        is_active=True
    ).order_by('-season_number').first()
    
    next_season = Season.objects.filter(
        series=series,
        season_number__gt=season_number,
        is_active=True
    ).order_by('season_number').first()
    
    return render(request, 'tv/season_detail.html', {
        'series': series,
        'season': season,
        'episodes': episodes,
        'prev_season': prev_season,
        'next_season': next_season,
        'page': 'series'
    })


def episode_player(request, series_slug, season_number, episode_number):
    """Spielt eine Episode ab"""
    series = get_object_or_404(Series, slug=series_slug, is_active=True)
    season = get_object_or_404(Season, series=series, season_number=season_number, is_active=True)
    episode = get_object_or_404(Episode, season=season, episode_number=episode_number, is_active=True)
    
    # Navigation
    next_episode = episode.get_next_episode()
    prev_episode = episode.get_previous_episode()
    
    # Andere Episoden dieser Staffel
    other_episodes = season.episodes.filter(is_active=True).exclude(id=episode.id).order_by('episode_number')[:6]
    
    # Streaming-URL bestimmen
    stream_url = episode.get_stream_url()
    
    return render(request, 'tv/episode_player.html', {
        'series': series,
        'season': season,
        'episode': episode,
        'stream_url': stream_url,
        'next_episode': next_episode,
        'prev_episode': prev_episode,
        'other_episodes': other_episodes,
        'page': 'series'
    })


def continue_watching(request):
    """Zeigt fortgesetzte/letzte gesehene Episoden (benötigt Session/Cookie-Tracking)"""
    # TODO: Session-basiertes oder User-basiertes Tracking implementieren
    # Für jetzt: Zeige neueste Episoden
    recent_episodes = Episode.objects.filter(
        is_active=True,
        season__is_active=True,
        season__series__is_active=True
    ).select_related('season', 'season__series').order_by('-created_at')[:12]
    
    return render(request, 'tv/continue_watching.html', {
        'episodes': recent_episodes,
        'page': 'series'
    })
