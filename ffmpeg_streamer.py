#!/usr/bin/env python3
"""
RSL TV – FFmpeg 24/7 Automatik-Stream (Verbesserte Version)
Joel Digitals

Verbesserungen:
 - KEIN Pillow mehr - nur FFmpeg
 - Automatischer Stream-Start zu YouTube/Twitch
 - Logo oben rechts (Senderlogo-Position)
 - Verbesserte Werbeblock-Verarbeitung
 - Endlos-Stream ohne Unterbrechung
 - Pausenbild-Unterstützung bei Sendepausen

Voraussetzungen:
    pip install requests yt-dlp python-dotenv
    apt install ffmpeg
"""

import os
import subprocess
import requests
import time
import json
import logging
import threading
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Konfiguration
API_URL        = os.environ.get('RSL_API_URL', 'http://localhost:8000')
YOUTUBE_KEY    = os.environ.get('YOUTUBE_STREAM_KEY', '')
TWITCH_KEY     = os.environ.get('TWITCH_STREAM_KEY', '')
FALLBACK_VIDEO = os.environ.get('FALLBACK_VIDEO', '')
STANDBY_IMAGE  = os.environ.get('STANDBY_IMAGE', '/home/claude/media/standby/default.png')
POLL_INTERVAL  = int(os.environ.get('POLL_INTERVAL', '10'))  # Sekunden
AUTO_START     = os.environ.get('AUTO_START_STREAM', 'true').lower() == 'true'

# Stream-Ziele
RTMP_TARGETS = []
if YOUTUBE_KEY:
    RTMP_TARGETS.append(f'rtmp://a.rtmp.youtube.com/live2/{YOUTUBE_KEY}')
if TWITCH_KEY:
    RTMP_TARGETS.append(f'rtmp://live.twitch.tv/app/{TWITCH_KEY}')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [RSL-TV] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rsl_stream.log')
    ],
)
log = logging.getLogger('RSL-TV')

# Globaler Prozess-Tracker
current_process = None
stream_running = False


def get_logo_info():
    """Holt Logo-Infos von der API"""
    try:
        r = requests.get(f'{API_URL}/api/logo/', timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and 'logo_path' in data:
                return data
    except Exception as e:
        log.debug(f"Logo-API-Fehler: {e}")
    return None


def build_logo_overlay_filter():
    """
    Erstellt FFmpeg-Filter für Logo-Overlay OBEN RECHTS
    Gibt (logo_inputs, filter_complex) zurück
    """
    logo_info = get_logo_info()
    
    if not logo_info or not os.path.exists(logo_info.get('logo_path', '')):
        # Kein Logo - nur Zeitstempel
        filter_complex = (
            "drawtext=text='%{localtime\\:%H\\:%M}':fontsize=18:fontcolor=white@0.4:"
            "x=15:y=h-th-15:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        return [], filter_complex
    
    logo_path = logo_info['logo_path']
    scale = logo_info.get('scale', 100)
    opacity = logo_info.get('opacity', 0.9)
    
    # Logo OBEN RECHTS
    filter_complex = (
        f"[1:v]scale={scale}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
        f"[0:v][logo]overlay=W-w-15:15[vlogo];"
        f"[vlogo]drawtext=text='%{{localtime\\:%H\\:%M}}':fontsize=18:fontcolor=white@0.4:"
        f"x=15:y=h-th-15:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf[vout]"
    )
    
    return ['-i', logo_path], filter_complex


def build_ffmpeg_command(input_url, is_loop=False, seek_seconds=0, duration=None, 
                         extra_filter='', is_image=False):
    """Erstellt FFmpeg-Befehl für Streaming"""
    logo_inputs, logo_filter = build_logo_overlay_filter()
    
    cmd = ['ffmpeg', '-loglevel', 'warning', '-stats']
    
    # Bild-Input?
    if is_image:
        cmd += ['-loop', '1', '-framerate', '25']
    elif is_loop:
        cmd += ['-stream_loop', '-1']
    
    if seek_seconds > 0:
        cmd += ['-ss', str(seek_seconds)]
    
    cmd += ['-re', '-i', input_url]
    cmd += logo_inputs  # Logo als zweiter Input
    
    # Filter kombinieren
    if logo_inputs:
        # Mit Logo
        if extra_filter:
            final_filter = f"{logo_filter};{extra_filter}"
        else:
            final_filter = logo_filter
        cmd += ['-filter_complex', final_filter, '-map', '[vout]']
    else:
        # Ohne Logo
        vf = logo_filter
        if extra_filter:
            vf = f"{extra_filter},{vf}"
        cmd += ['-vf', vf]
    
    # Audio
    if is_image:
        # Stilles Audio für Bilder generieren
        cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo']
        cmd += ['-map', '1:a']
    else:
        cmd += ['-map', '0:a?']
    
    if duration:
        cmd += ['-t', str(duration)]
    
    # Encoding-Einstellungen
    cmd += [
        '-c:v', 'libx264', '-preset', 'veryfast',
        '-maxrate', '4000k', '-bufsize', '8000k',
        '-pix_fmt', 'yuv420p', '-g', '50',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
        '-shortest'  # Stoppt wenn kürzester Stream endet
    ]
    
    # Output
    if len(RTMP_TARGETS) == 1:
        cmd += ['-f', 'flv', RTMP_TARGETS[0]]
    elif len(RTMP_TARGETS) > 1:
        tee = '|'.join([f'[f=flv]{t}' for t in RTMP_TARGETS])
        cmd += ['-f', 'tee', tee]
    else:
        # Kein Ziel - Testmodus
        cmd += ['-f', 'null', '-']
    
    return cmd


def resolve_video_url(url):
    """Versucht streambare URL zu ermitteln"""
    if not url:
        return None
    
    # YouTube
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            result = subprocess.run(
                ['yt-dlp', '-g', '-f', 'best[ext=mp4]/best', url],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception as e:
            log.warning(f"yt-dlp Fehler: {e}")
            return None
    
    # Dropbox
    elif 'dropbox.com' in url:
        return url.replace('?dl=0', '?dl=1').replace('www.dropbox.com', 'dl.dropboxusercontent.com')
    
    # Google Drive
    elif 'drive.google.com' in url and '/d/' in url:
        file_id = url.split('/d/')[1].split('/')[0]
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    return url


def start_stream_process(cmd, description="Stream"):
    """Startet FFmpeg-Prozess"""
    global current_process, stream_running
    
    try:
        log.info(f"▶️  {description}")
        log.debug(f"FFmpeg CMD: {' '.join(cmd)}")
        
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stream_running = True
        return current_process
    except Exception as e:
        log.error(f"Fehler beim Starten: {e}")
        stream_running = False
        return None


def stop_stream_process():
    """Stoppt aktuellen Stream-Prozess"""
    global current_process, stream_running
    
    if current_process:
        try:
            current_process.terminate()
            current_process.wait(timeout=5)
        except Exception:
            try:
                current_process.kill()
            except Exception:
                pass
        current_process = None
    stream_running = False


def play_video(url, title='', start_seconds=0, duration=None):
    """Spielt ein Video ab"""
    resolved_url = resolve_video_url(url)
    if not resolved_url:
        log.error(f"Konnte URL nicht auflösen: {url}")
        return False
    
    cmd = build_ffmpeg_command(
        resolved_url,
        seek_seconds=start_seconds,
        duration=duration
    )
    
    proc = start_stream_process(cmd, f"Video: {title or url[:50]}")
    if not proc:
        return False
    
    try:
        proc.wait()
        return True
    except KeyboardInterrupt:
        stop_stream_process()
        raise
    except Exception as e:
        log.error(f"Video-Fehler: {e}")
        return False


def play_live_stream(url, title=''):
    """Spielt Live-Stream mit LIVE-Badge"""
    resolved_url = resolve_video_url(url)
    if not resolved_url:
        log.error(f"Konnte Live-URL nicht auflösen: {url}")
        return False
    
    # LIVE-Badge Filter
    live_badge = (
        "drawbox=x=15:y=15:w=100:h=35:color=red@0.9:t=fill,"
        "drawtext=text='🔴 LIVE':fontsize=20:fontcolor=white:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:x=25:y=23"
    )
    
    cmd = build_ffmpeg_command(resolved_url, extra_filter=live_badge)
    
    proc = start_stream_process(cmd, f"🔴 LIVE: {title}")
    if not proc:
        return False
    
    # Überwache Live-Stream und prüfe auf Werbepausen
    while proc.poll() is None:
        time.sleep(POLL_INTERVAL)
        
        # Prüfe API auf Änderungen
        playlist = get_playlist_data()
        if not playlist:
            continue
        
        ptype = playlist.get('type')
        
        if ptype == 'live_ad_break':
            log.info("🎯 Live-Werbepause erkannt!")
            stop_stream_process()
            play_ad_block(playlist.get('ads', []))
            return True  # Zur Hauptschleife zurück
        
        elif ptype != 'live':
            log.info("Live-Stream beendet (laut API)")
            stop_stream_process()
            return True
    
    return True


def play_ad_block(ads):
    """Spielt Werbeblock ab"""
    if not ads:
        log.info("Leerer Werbeblock übersprungen")
        return
    
    log.info(f"🎯 Werbeblock: {len(ads)} Video(s)")
    
    for ad in ads:
        ad_title = ad.get('title', 'Werbung')
        ad_url = ad.get('url', '')
        ad_duration = ad.get('duration', 30)
        ad_type = ad.get('ad_type', 'spot')
        
        type_label = {
            'trailer': '📺 TRAILER',
            'spot': '📢 SPOT',
            'outro': '🎬 OUTRO'
        }.get(ad_type, '📢 AD')
        
        log.info(f"  {type_label}: {ad_title} ({ad_duration}s)")
        
        resolved_url = resolve_video_url(ad_url)
        if not resolved_url:
            log.warning(f"Konnte Werbe-URL nicht auflösen: {ad_url}")
            continue
        
        cmd = build_ffmpeg_command(resolved_url, duration=ad_duration)
        proc = start_stream_process(cmd, f"{type_label}: {ad_title}")
        
        if proc:
            try:
                proc.wait(timeout=ad_duration + 10)
            except subprocess.TimeoutExpired:
                stop_stream_process()
            except Exception as e:
                log.error(f"Werbe-Fehler: {e}")
                stop_stream_process()
    
    log.info("✅ Werbeblock beendet")


def play_standby_image(duration=300):
    """Zeigt Pausenbild an"""
    standby = get_standby_image()
    if not standby or not os.path.exists(standby):
        log.warning("Kein Pausenbild verfügbar - zeige Fallback")
        time.sleep(5)
        return
    
    log.info(f"📺 Pausenbild ({duration}s)")
    
    cmd = build_ffmpeg_command(
        standby,
        is_image=True,
        duration=duration
    )
    
    proc = start_stream_process(cmd, "Pausenbild")
    if proc:
        try:
            proc.wait(timeout=duration + 5)
        except subprocess.TimeoutExpired:
            stop_stream_process()
        except Exception as e:
            log.error(f"Pausenbild-Fehler: {e}")
            stop_stream_process()


def get_standby_image():
    """Holt Pausenbild von API oder verwendet Standard"""
    try:
        r = requests.get(f'{API_URL}/api/standby/', timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and 'image_path' in data:
                return data['image_path']
    except Exception:
        pass
    
    # Fallback
    if os.path.exists(STANDBY_IMAGE):
        return STANDBY_IMAGE
    
    return None


def get_playlist_data():
    """Holt Playlist-Daten von API"""
    try:
        r = requests.get(f'{API_URL}/api/playlist/', timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.error(f"API-Fehler: {e}")
    return None


def handle_scheduled_content(data):
    """Behandelt geplante Sendung"""
    url = data.get('video_url', '')
    title = data.get('title', 'Sendung')
    start_at = data.get('start_seconds', 0)
    
    resolved_url = resolve_video_url(url)
    if not resolved_url:
        log.error(f"Konnte Video-URL nicht auflösen: {url}")
        return
    
    cmd = build_ffmpeg_command(resolved_url, seek_seconds=start_at)
    proc = start_stream_process(cmd, f"📺 {title}")
    
    if not proc:
        return
    
    # Überwache auf Werbepausen und Live-Schaltungen
    while proc.poll() is None:
        time.sleep(POLL_INTERVAL)
        
        playlist = get_playlist_data()
        if not playlist:
            continue
        
        ptype = playlist.get('type')
        
        if ptype == 'live':
            log.info("Live-Schaltung erkannt - beende Video")
            stop_stream_process()
            return
        
        elif ptype == 'scheduled_ad_break':
            log.info("🎯 Geplante Werbepause erkannt!")
            stop_stream_process()
            play_ad_block(playlist.get('ads', []))
            # Setze Video fort
            resume_at = playlist.get('resume_at_seconds', start_at)
            data['start_seconds'] = resume_at
            handle_scheduled_content(data)
            return


def main_loop():
    """Haupt-Stream-Schleife"""
    log.info("=" * 60)
    log.info("🎬  RSL TV 24/7 STREAM GESTARTET")
    log.info(f"📡  Stream-Ziele: {len(RTMP_TARGETS)}")
    for target in RTMP_TARGETS:
        platform = 'YouTube' if 'youtube' in target else 'Twitch' if 'twitch' in target else 'Custom'
        log.info(f"    ▶️  {platform}")
    log.info(f"🔗  API: {API_URL}")
    log.info(f"⏱️   Poll-Intervall: {POLL_INTERVAL}s")
    log.info("=" * 60)
    
    if not RTMP_TARGETS:
        log.error("❌ KEINE STREAM-ZIELE KONFIGURIERT!")
        log.error("Setzen Sie YOUTUBE_STREAM_KEY oder TWITCH_STREAM_KEY in .env")
        return
    
    iteration = 0
    
    while True:
        try:
            iteration += 1
            log.info(f"\n[Iteration #{iteration}] Rufe Playlist ab...")
            
            playlist = get_playlist_data()
            
            if not playlist or playlist.get('type') == 'empty':
                log.info("📺 Keine Sendung - zeige Pausenbild")
                play_standby_image(duration=60)
                continue
            
            ptype = playlist.get('type')
            log.info(f"📋 Playlist-Typ: {ptype}")
            
            # LIVE
            if ptype == 'live':
                play_live_stream(
                    playlist.get('stream_url', ''),
                    playlist.get('title', 'Live')
                )
            
            # LIVE WERBEPAUSE
            elif ptype == 'live_ad_break':
                play_ad_block(playlist.get('ads', []))
            
            # GEPLANTE SENDUNG
            elif ptype == 'scheduled':
                handle_scheduled_content(playlist)
            
            # GEPLANTE WERBEPAUSE
            elif ptype == 'scheduled_ad_break':
                play_ad_block(playlist.get('ads', []))
            
            # PLAYLIST
            elif ptype == 'playlist':
                items = playlist.get('items', [])
                for item in items:
                    if item.get('type') == 'ad_break':
                        play_ad_block(item.get('ads', []))
                    else:
                        play_video(
                            item.get('url', ''),
                            item.get('title', ''),
                            duration=item.get('duration')
                        )
            
            # UNBEKANNT
            else:
                log.warning(f"Unbekannter Playlist-Typ: {ptype}")
                play_standby_image(duration=30)
        
        except KeyboardInterrupt:
            log.info("\n⏹️  Stream manuell gestoppt (Ctrl+C)")
            stop_stream_process()
            break
        
        except Exception as e:
            log.error(f"❌ Fehler in Hauptschleife: {e}", exc_info=True)
            log.info("Warte 10 Sekunden vor Neustart...")
            time.sleep(10)
    
    log.info("🏁 Stream beendet")


if __name__ == '__main__':
    try:
        main_loop()
    except KeyboardInterrupt:
        log.info("\n👋 Auf Wiedersehen!")
        stop_stream_process()
        sys.exit(0)