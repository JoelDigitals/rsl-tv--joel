#!/usr/bin/env python3
"""
RSL TV – FFmpeg 24/7 Automatik-Stream (vollständig überarbeitet)
Joel Digitals

Features:
 - Logo-Wasserzeichen (oben links/rechts) aus hochgeladener Datei
 - Werbepausen: Video wird PAUSIERT, Werbeblock läuft, danach Fortsetzung
 - Trailer-Spot + Hauptspots + Outro-Spot automatisch zusammengestellt
 - Live-Schaltung mit Live-Badge im Stream
 - Manuelle Live-Werbepausen über Admin-Button
 - Uhrzeit-Einblendung im Stream

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
import tempfile
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_URL        = os.environ.get('RSL_API_URL', 'http://localhost:8000')
YOUTUBE_KEY    = os.environ.get('YOUTUBE_STREAM_KEY', '')
TWITCH_KEY     = os.environ.get('TWITCH_STREAM_KEY', '')
FALLBACK_VIDEO = os.environ.get('FALLBACK_VIDEO', '')
POLL_INTERVAL  = int(os.environ.get('POLL_INTERVAL', '15'))  # Sekunden

RTMP_TARGETS = []
if YOUTUBE_KEY:
    RTMP_TARGETS.append(f'rtmp://a.rtmp.youtube.com/live2/{YOUTUBE_KEY}')
if TWITCH_KEY:
    RTMP_TARGETS.append(f'rtmp://live.twitch.tv/app/{TWITCH_KEY}')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [RSL] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('rsl_stream.log')],
)
log = logging.getLogger('RSL')

# ─── LOGO LADEN ──────────────────────────────────────────────────────────

def get_logo_info():
    """Holt Logo-Infos von der API"""
    try:
        r = requests.get(f'{API_URL}/api/logo/', timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

_logo_cache = None
_logo_cache_time = 0

def get_logo_filter(video_filter_out='[v]'):
    """
    Baut den FFmpeg Logo-Overlay-Filter.
    Gibt (input_args, filter_complex, output_map) zurück.
    """
    global _logo_cache, _logo_cache_time
    now = time.time()
    if now - _logo_cache_time > 300:  # alle 5 Min neu laden
        _logo_cache = get_logo_info()
        _logo_cache_time = now

    logo = _logo_cache
    if not logo or not os.path.exists(logo.get('logo_path', '')):
        # Kein Logo – nur Timestamp + Watermark-Text
        f = (
            "drawtext=text='RSL':fontsize=22:fontcolor=white@0.45:"
            "x=w-tw-18:y=18:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,"
            "drawtext=text='%{localtime\\:%H\\:%M}':fontsize=16:fontcolor=white@0.35:"
            "x=18:y=h-th-18:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        return [], f, None

    logo_path = logo['logo_path']
    scale     = logo.get('scale', 80)
    opacity   = logo.get('opacity', 0.85)
    overlay   = logo.get('overlay', 'overlay=W-w-10:10')

    filter_complex = (
        f"[1:v]scale={scale}:-1,format=rgba,colorchannelmixer=aa={opacity}[logo];"
        f"[0:v][logo]{overlay}[vlogo];"
        f"[vlogo]drawtext=text='%{{localtime\\:%H\\:%M}}':fontsize=16:fontcolor=white@0.35:"
        f"x=18:y=h-th-18:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf[{video_filter_out[1:-1]}]"
    )
    return ['-i', logo_path], filter_complex, video_filter_out


def build_stream_cmd(input_url, targets, extra_filters='', is_loop=False, seek_seconds=0, duration=None):
    """Generiert kompletten FFmpeg-Befehl"""
    logo_inputs, logo_filter, logo_out = get_logo_filter()

    cmd = ['ffmpeg', '-loglevel', 'warning', '-stats']

    if is_loop:
        cmd += ['-stream_loop', '-1']
    if seek_seconds > 0:
        cmd += ['-ss', str(seek_seconds)]

    cmd += ['-re', '-i', input_url]
    cmd += logo_inputs  # ggf. Logo als zweiter Input

    if logo_out:
        # Mit Logo-Overlay
        if extra_filters:
            fc = f"{logo_filter};{extra_filters}"
        else:
            fc = logo_filter
        cmd += ['-filter_complex', fc, '-map', logo_out, '-map', '0:a?']
    else:
        # Ohne Logo-Datei – nur Text-Overlay
        vf = logo_filter
        if extra_filters:
            vf = f"{extra_filters},{vf}"
        cmd += ['-vf', vf]

    if duration:
        cmd += ['-t', str(duration)]

    cmd += [
        '-c:v', 'libx264', '-preset', 'veryfast',
        '-maxrate', '3000k', '-bufsize', '6000k',
        '-pix_fmt', 'yuv420p', '-g', '50',
        '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
    ]

    if len(targets) == 1:
        cmd += ['-f', 'flv', targets[0]]
    else:
        tee = '|'.join([f'[f=flv]{t}' for t in targets])
        cmd += ['-f', 'tee', tee]

    return cmd


# ─── LIVE-BADGE FILTER ────────────────────────────────────────────────────

LIVE_BADGE_FILTER = (
    "drawbox=x=10:y=10:w=90:h=28:color=red@0.85:t=fill,"
    "drawtext=text='🔴 LIVE':fontsize=16:fontcolor=white:"
    "x=18:y=18:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)


# ─── URL AUFLÖSUNG ────────────────────────────────────────────────────────

def resolve_url(url):
    """Versucht streambare URL zu ermitteln"""
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            r = subprocess.run(
                ['yt-dlp', '-g', '-f', 'best[ext=mp4]/best', url],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return r.stdout.strip().split('\n')[0]
        except Exception as e:
            log.warning(f"yt-dlp: {e}")
    elif 'dropbox.com' in url:
        return url.replace('?dl=0', '?dl=1').replace('www.dropbox.com', 'dl.dropboxusercontent.com')
    elif 'drive.google.com' in url and '/d/' in url:
        fid = url.split('/d/')[1].split('/')[0]
        return f"https://drive.google.com/uc?export=download&id={fid}"
    return url


# ─── WERBEBLOCK ABSPIELEN ────────────────────────────────────────────────

def play_ad_block(ads):
    """
    Spielt einen vollständigen Werbeblock ab:
    [Trailer] → [Spots] → [Outro]
    Das Hauptprogramm ist während dieser Zeit unterbrochen.
    """
    if not ads:
        log.info("Werbeblock: leer")
        return

    log.info(f"🎯 Werbeblock startet: {len(ads)} Videos")
    for ad in ads:
        title = ad.get('title', '?')
        ad_type = ad.get('ad_type', 'spot')
        url = resolve_url(ad['url'])
        dur = ad.get('duration', 30)

        type_label = {'trailer': 'TRAILER', 'spot': 'SPOT', 'outro': 'OUTRO'}.get(ad_type, 'AD')
        log.info(f"  [{type_label}] {title} ({dur}s)")

        cmd = build_stream_cmd(url, RTMP_TARGETS, duration=dur)
        try:
            proc = subprocess.Popen(cmd)
            proc.wait(timeout=dur + 15)
        except subprocess.TimeoutExpired:
            proc.terminate()
        except Exception as e:
            log.error(f"Werbe-Fehler: {e}")

    log.info("✅ Werbeblock beendet – Hauptprogramm wird fortgesetzt")


# ─── VIDEO STREAMEN ───────────────────────────────────────────────────────

def stream_video(url, title='', start_seconds=0, duration=None):
    """Streamt ein Video (ggf. ab bestimmter Position)"""
    log.info(f"▶️  {title or url[:60]}" + (f" (ab {start_seconds}s)" if start_seconds else ''))
    real_url = resolve_url(url)
    cmd = build_stream_cmd(real_url, RTMP_TARGETS, seek_seconds=start_seconds, duration=duration)
    try:
        proc = subprocess.Popen(cmd)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        raise
    except Exception as e:
        log.error(f"Video-Fehler: {e}")


def stream_live(url, title=''):
    """Streamt einen Live-Feed mit LIVE-Badge"""
    log.info(f"🔴 LIVE: {title}")
    real_url = resolve_url(url)
    cmd = build_stream_cmd(real_url, RTMP_TARGETS, extra_filters=LIVE_BADGE_FILTER)
    try:
        proc = subprocess.Popen(cmd)

        while proc.poll() is None:
            time.sleep(POLL_INTERVAL)
            data = _get_playlist()
            if not data:
                continue
            t = data.get('type')
            if t == 'live_ad_break':
                log.info("🎯 Live-Werbepause erkannt!")
                proc.terminate()
                proc.wait()
                play_ad_block(data.get('ads', []))
                # Danach zurück zu Live
                return  # Hauptschleife entscheidet weiter
            elif t != 'live' and t != 'live_ad_break':
                log.info("Live beendet laut API")
                proc.terminate()
                break

    except KeyboardInterrupt:
        proc.terminate()
        raise
    except Exception as e:
        log.error(f"Live-Fehler: {e}")


def stream_scheduled(data):
    """
    Streamt eine geplante Sendung.
    Wenn eine Werbepause fällig ist, pausiert das Video und spielt den Block.
    """
    url = data.get('video_url', '')
    title = data.get('title', '')
    start_at = data.get('start_seconds', 0)
    ends_at_str = data.get('ends_at', '')

    # Berechne restliche Dauer
    total_remaining = None
    if ends_at_str:
        from datetime import datetime, timezone as tz
        try:
            ends = datetime.fromisoformat(ends_at_str.replace('Z', '+00:00'))
            now = datetime.now(tz.utc)
            total_remaining = max(0, int((ends - now).total_seconds()))
        except Exception:
            pass

    real_url = resolve_url(url)
    cmd = build_stream_cmd(real_url, RTMP_TARGETS, seek_seconds=start_at, duration=total_remaining)

    log.info(f"📺 Geplant: {title}" + (f" ({total_remaining}s)" if total_remaining else ''))

    try:
        proc = subprocess.Popen(cmd)

        while proc.poll() is None:
            time.sleep(POLL_INTERVAL)
            api_data = _get_playlist()
            if not api_data:
                continue

            t = api_data.get('type')
            if t == 'live':
                log.info("Live-Schaltung erkannt – breche Video ab")
                proc.terminate()
                return
            elif t == 'scheduled_ad_break':
                log.info("🎯 Geplante Werbepause erkannt – Video pausiert!")
                proc.terminate()
                proc.wait()
                play_ad_block(api_data.get('ads', []))
                # Danach: Video fortsetzen ab aktueller Position
                resume_at = api_data.get('resume_at_seconds', start_at)
                stream_scheduled({**data, 'start_seconds': resume_at})
                return

    except KeyboardInterrupt:
        proc.terminate()
        raise
    except Exception as e:
        log.error(f"Schedule-Fehler: {e}")


def stream_fallback():
    """Sendepause – Fallback Video in Loop"""
    log.info("📟 Sendepause")
    if not FALLBACK_VIDEO:
        time.sleep(30)
        return
    cmd = build_stream_cmd(FALLBACK_VIDEO, RTMP_TARGETS, is_loop=True, duration=300)
    try:
        proc = subprocess.Popen(cmd)
        proc.wait(timeout=310)
    except subprocess.TimeoutExpired:
        proc.terminate()
    except Exception as e:
        log.error(f"Fallback-Fehler: {e}")
        time.sleep(10)


# ─── PLAYLIST ABRUF ───────────────────────────────────────────────────────

def _get_playlist():
    try:
        r = requests.get(f'{API_URL}/api/playlist/', timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"API-Fehler: {e}")
        return None


# ─── HAUPTSCHLEIFE ────────────────────────────────────────────────────────

def main():
    log.info("=" * 55)
    log.info("🎬  RSL TV STREAM – Joel Digitals")
    log.info(f"📡  Ziele: {RTMP_TARGETS}")
    log.info(f"🔗  API:   {API_URL}")
    log.info("=" * 55)

    if not RTMP_TARGETS:
        log.error("Keine Stream-Ziele! YOUTUBE_STREAM_KEY oder TWITCH_STREAM_KEY setzen.")
        return

    while True:
        try:
            data = _get_playlist()

            if not data:
                stream_fallback()
                continue

            t = data.get('type')

            if t == 'live':
                stream_live(data['stream_url'], data.get('title', 'Live'))

            elif t == 'live_ad_break':
                play_ad_block(data.get('ads', []))

            elif t == 'scheduled':
                stream_scheduled(data)

            elif t == 'scheduled_ad_break':
                play_ad_block(data.get('ads', []))
                after = data.get('video_url')
                if after:
                    stream_scheduled(data)

            elif t == 'playlist':
                for item in data.get('items', []):
                    if item.get('type') == 'ad_break':
                        play_ad_block(item.get('ads', []))
                    else:
                        stream_video(item.get('url', ''), item.get('title', ''), duration=item.get('duration'))

            else:
                stream_fallback()

        except KeyboardInterrupt:
            log.info("Manuell gestoppt.")
            break
        except Exception as e:
            log.error(f"Hauptschleife: {e}")
            time.sleep(10)


if __name__ == '__main__':
    main()
