"""
TV API Views - KOMPLETT FUNKTIONIEREND
=======================================
Diese Datei am ENDE von tv/views.py einfügen!
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json


# ============================================================================
# WERBEPAUSEN APIs
# ============================================================================

@require_http_methods(["GET"])
def api_ad_break_status(request):
    """
    API: Werbepausen-Status
    GET /api/ad-break-status/
    """
    try:
        # Direkt importieren statt from tv.models
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
@require_http_methods(["POST"])
def api_start_ad_break(request):
    """
    API: Werbepause starten
    POST /api/ad-break/start/
    """
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
@require_http_methods(["POST"])
def api_end_ad_break(request):
    """
    API: Werbepause beenden
    POST /api/ad-break/end/
    """
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

@require_http_methods(["GET"])
def program_room_status_api(request):
    """
    GET /api/program/status/
    """
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
        
        youtube_live = room.is_streaming_youtube and bool(room.youtube_stream_key)
        twitch_live = room.is_streaming_twitch and bool(room.twitch_stream_key)
        
        # FFmpeg läuft? (nur als Info)
        ffmpeg_running = False
        try:
            import subprocess
            result = subprocess.run(['pgrep', '-f', 'python.*streamer'], 
                                   capture_output=True, text=True, timeout=2)
            ffmpeg_running = bool(result.stdout.strip())
        except:
            pass
        
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


@csrf_exempt
@require_http_methods(["POST"])
def program_room_save_keys_api(request):
    """
    POST /api/program/save-keys/
    """
    try:
        data = json.loads(request.body) if request.body else request.POST.dict()
        room, _ = ProgramRoom.objects.get_or_create(id=1)
        
        if 'youtube_key' in data:
            room.youtube_stream_key = data['youtube_key']
        if 'youtube_rtmp' in data:
            room.youtube_rtmp_url = data['youtube_rtmp']
        if 'twitch_key' in data:
            room.twitch_stream_key = data['twitch_key']
        if 'twitch_rtmp' in data:
            room.twitch_rtmp_url = data['twitch_rtmp']
        
        room.save()
        return JsonResponse({'success': True, 'message': 'Keys gespeichert'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)