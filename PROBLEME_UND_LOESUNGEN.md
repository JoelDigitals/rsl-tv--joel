# RSL TV - Problemanalyse und Lösungen

## 📋 Probleme im Überblick

1. ❌ Stream zu Twitch funktioniert nicht
2. ❌ YouTube in der Mediathek funktioniert nicht
3. ❌ Stream zu YouTube funktioniert nicht
4. ❌ YouTube-Sendung im TV muss auf Render-Server abgespielt werden (nicht vorspulbar, Werbepausen-Kontrolle)

---

## 🔍 Problem 1: Stream zu Twitch funktioniert nicht

### Diagnose
Nach Analyse des Codes in `python_streamer.py` (Zeile 512-515 und 526-529):

**DirectorRoom:**
```python
if self.director_room.is_streaming_twitch and self.director_room.twitch_stream_key:
    rtmp_url = f"rtmp://live.twitch.tv/app/{self.director_room.twitch_stream_key}"
    streamer = RTMPStreamer(rtmp_url, self.width, self.height, self.fps, self.bitrate, 'Twitch')
```

**ProgramRoom:**
```python
if self.program_room.is_streaming_twitch and self.program_room.twitch_stream_key:
    rtmp_url = f"{self.program_room.twitch_rtmp_url}/{self.program_room.twitch_stream_key}"
    streamer = RTMPStreamer(rtmp_url, self.width, self.height, self.fps, self.bitrate, 'Twitch')
```

### Probleme gefunden:

1. **DirectorRoom:** Hardcodierte RTMP URL ist korrekt
2. **ProgramRoom:** Nutzt `program_room.twitch_rtmp_url` aus der Datenbank (Zeile 1129-1130 in models.py)
3. **Stream-Key Format:** Möglicherweise falsch formatiert
4. **Fehlende Validierung:** Keine Prüfung ob FFmpeg läuft
5. **Server-Auswahl:** Twitch hat verschiedene Ingest-Server

### Lösung:

#### A) Datenbank-Konfiguration prüfen
```python
# In Django Shell:
from tv.models import ProgramRoom, DirectorRoom

# Für ProgramRoom
room = ProgramRoom.objects.first()
print(f"Twitch RTMP: {room.twitch_rtmp_url}")
print(f"Twitch Key: {room.twitch_stream_key}")

# Sollte sein:
room.twitch_rtmp_url = "rtmp://live.twitch.tv/app"
room.save()

# Für DirectorRoom
director = DirectorRoom.objects.first()
print(f"Twitch Key: {director.twitch_stream_key}")
```

#### B) Twitch Ingest-Server optimieren
Twitch hat verschiedene Server. Teste den besten:
- `rtmp://live.twitch.tv/app` (Auto)
- `rtmp://fra02.contribute.live-video.net/app` (Frankfurt - näher zu DE)
- `rtmp://ams02.contribute.live-video.net/app` (Amsterdam)

#### C) Stream-Key Format
Twitch Stream-Keys beginnen meist mit `live_` gefolgt von einer langen Zeichenkette:
```
live_123456789_abcdefghijklmnopqrstuvwxyz
```

#### D) FFmpeg Kommando optimieren
In `python_streamer.py` Zeile 251-269 ist das FFmpeg-Kommando. Für Twitch empfohlen:

```python
command = [
    'ffmpeg',
    '-f', 'rawvideo',
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-s', f'{self.width}x{self.height}',
    '-r', str(self.fps),
    '-i', '-',
    # Video Encoding
    '-c:v', 'libx264',
    '-preset', 'veryfast',  # ultrafast → veryfast für bessere Qualität
    '-tune', 'zerolatency',  # Für Live-Streaming
    '-b:v', self.bitrate,
    '-maxrate', self.bitrate,
    '-bufsize', f'{int(self.bitrate.replace("k","")) * 2}k',
    '-pix_fmt', 'yuv420p',
    '-g', '60',  # Keyframe alle 2 Sekunden bei 30fps
    '-keyint_min', '60',
    # Audio (wichtig für Twitch!)
    '-f', 'lavfi',
    '-i', 'anullsrc',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-ar', '44100',
    # Output
    '-f', 'flv',
    self.rtmp_url
]
```

**WICHTIG:** Twitch erfordert Audio! Ohne Audio-Stream wird die Verbindung oft abgelehnt.

---

## 🔍 Problem 2: YouTube in der Mediathek funktioniert nicht

### Diagnose
In `mediathek.html` Zeile 262-267:

```javascript
if (videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be')) {
    const videoIdMatch = videoUrl.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu.be\/)([^"&?\/\s]{11})/);
    if (videoIdMatch) {
        player.src = `https://www.youtube.com/embed/${videoIdMatch[1]}?autoplay=1&modestbranding=1&rel=0`;
    }
}
```

### Probleme:

1. **YouTube Embed-Restrictions:** YouTube blockiert Embeds von unbekannten Domains
2. **Domain-Whitelist:** Bei Render.com muss die Domain in YouTube erlaubt sein
3. **Cookies/GDPR:** YouTube verlangt Cookie-Consent
4. **Fallback fehlt:** Wenn Regex fehlschlägt, bleibt Player leer

### Lösung:

#### A) Verwende YouTube Nocookie Domain
```javascript
// Alt:
player.src = `https://www.youtube.com/embed/${videoIdMatch[1]}?autoplay=1`;

// Neu:
player.src = `https://www.youtube-nocookie.com/embed/${videoIdMatch[1]}?autoplay=1&modestbranding=1&rel=0&origin=${window.location.origin}`;
```

#### B) Verbesserte Video-URL Erkennung
```javascript
function playVideo(videoId, videoUrl) {
    const modal = new bootstrap.Modal(document.getElementById('videoModal'));
    const player = document.getElementById('videoPlayer');
    
    console.log('Playing video:', videoUrl);  // Debug
    
    // YouTube
    if (videoUrl.includes('youtube.com') || videoUrl.includes('youtu.be')) {
        let videoId = null;
        
        // Verschiedene YouTube URL Formate
        if (videoUrl.includes('v=')) {
            videoId = videoUrl.split('v=')[1].split('&')[0];
        } else if (videoUrl.includes('youtu.be/')) {
            videoId = videoUrl.split('youtu.be/')[1].split('?')[0];
        } else if (videoUrl.includes('/embed/')) {
            videoId = videoUrl.split('/embed/')[1].split('?')[0];
        }
        
        if (videoId) {
            player.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&modestbranding=1&rel=0&origin=${encodeURIComponent(window.location.origin)}`;
        } else {
            console.error('Konnte YouTube Video-ID nicht extrahieren:', videoUrl);
            alert('Fehler beim Laden des Videos');
        }
    }
    // Twitch
    else if (videoUrl.includes('twitch.tv')) {
        const parts = videoUrl.split('twitch.tv/')[1];
        if (parts.startsWith('videos/')) {
            const videoId = parts.replace('videos/', '');
            player.src = `https://player.twitch.tv/?video=${videoId}&parent=${window.location.hostname}&autoplay=true`;
        } else {
            // Live Channel
            player.src = `https://player.twitch.tv/?channel=${parts}&parent=${window.location.hostname}&autoplay=true`;
        }
    }
    // Direkte URL (MP4, etc.)
    else {
        player.src = videoUrl;
    }
    
    modal.show();
}
```

#### C) Model-Methode verbessern
In `tv/models.py` bei der `Video.get_stream_url()` Methode:

```python
def get_stream_url(self):
    """Gibt die bereinigte Stream-URL zurück"""
    if not self.video_url:
        return ''
    
    url = self.video_url.strip()
    
    # YouTube
    if 'youtube.com' in url or 'youtu.be' in url:
        # Extrahiere Video-ID
        import re
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'youtu\.be/([0-9A-Za-z_-]{11})',
            r'embed/([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                # Gebe die volle YouTube URL zurück, nicht embed
                return f'https://www.youtube.com/watch?v={video_id}'
        
    return url
```

---

## 🔍 Problem 3: Stream zu YouTube funktioniert nicht

### Diagnose

Ähnliche Ursachen wie bei Twitch, plus:

1. **YouTube RTMP Server:** Nutzt `a.rtmp.youtube.com/live2`
2. **Stream-Key Format:** Unterscheidet sich von Twitch
3. **Latenz-Einstellungen:** YouTube hat verschiedene Modi
4. **Audio erforderlich:** Wie bei Twitch

### Lösung:

#### A) Korrekte RTMP URL
```python
# In python_streamer.py
# YouTube (Zeile 508-511 und 519-523):
rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{self.youtube_stream_key}"
```

Alternativen für bessere Performance:
- `rtmp://a.rtmp.youtube.com/live2` (Auto)
- `rtmp://fra.contribute.live-video.net/app` (Frankfurt)

#### B) Stream-Key Validierung
YouTube Stream-Keys sind meistens länger und haben spezifisches Format.

#### C) YouTube Studio korrekt konfigurieren
1. YouTube Studio → Live → Stream-Einstellungen
2. **Latenz:** "Normal" oder "Niedrig" (nicht Ultra-niedrig)
3. **Automatische Wiederverbindung:** Aktivieren
4. **DVR aktivieren:** Optional
5. **Stream-Optimierung:** 1080p, 30fps empfohlen

---

## 🔍 Problem 4: YouTube-Sendung im TV (nicht vorspulbar, Werbepausen-Kontrolle)

### Anforderungen:

1. ✅ YouTube-Video auf eigenem Render-Server abspielen
2. ✅ Nicht vorspulbar
3. ✅ Bei Werbepausen anhalten
4. ✅ Nach Werbepause exakt an gleicher Stelle fortsetzen
5. ✅ Kein YouTube Logo, Keine Bedienelemente sichtbar

### Lösung: Eigener Video-Proxy mit YouTube-DL

Da YouTube-Embeds nicht vollständig kontrollierbar sind, brauchen Sie einen Video-Proxy.

#### A) Backend: Video-Download Endpoint

Erstelle `tv/youtube_proxy.py`:

```python
import os
import subprocess
import tempfile
from pathlib import Path
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
import yt_dlp

CACHE_DIR = Path('/tmp/rsl_video_cache')
CACHE_DIR.mkdir(exist_ok=True)

def get_video_info(youtube_url):
    """Holt Video-Informationen ohne Download"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        
        # Finde bestes Video-Format (max 1080p für Performance)
        formats = info.get('formats', [])
        video_format = None
        
        for f in formats:
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                height = f.get('height', 0)
                if height <= 1080 and height > 0:
                    if video_format is None or f.get('height', 0) > video_format.get('height', 0):
                        video_format = f
        
        if not video_format:
            # Fallback: Beste Video + Beste Audio kombinieren
            video_format = max([f for f in formats if f.get('vcodec') != 'none'], 
                             key=lambda x: x.get('height', 0))
        
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),
            'url': video_format.get('url'),
            'format_id': video_format.get('format_id'),
            'width': video_format.get('width'),
            'height': video_format.get('height'),
        }

@require_http_methods(['GET'])
def proxy_youtube_video(request):
    """Proxy für YouTube Videos - ermöglicht Kontrolle"""
    youtube_url = request.GET.get('url')
    
    if not youtube_url:
        return JsonResponse({'error': 'URL required'}, status=400)
    
    try:
        # Video-Info holen
        info = get_video_info(youtube_url)
        
        # Direkte URL streamen (kein Download nötig!)
        video_url = info['url']
        
        # Starte FFmpeg zum Re-Encoding (wichtig für Kontrolle)
        command = [
            'ffmpeg',
            '-i', video_url,
            '-c:v', 'copy',  # Video kopieren (schnell)
            '-c:a', 'copy',  # Audio kopieren
            '-f', 'mp4',
            '-movflags', 'frag_keyframe+empty_moov',  # Streaming-fähig
            '-'  # Output zu stdout
        ]
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        def stream_video():
            try:
                while True:
                    chunk = process.stdout.read(8192)
                    if not chunk:
                        break
                    yield chunk
            finally:
                process.terminate()
        
        response = StreamingHttpResponse(
            stream_video(),
            content_type='video/mp4'
        )
        response['Accept-Ranges'] = 'none'  # Deaktiviert Vorspulen!
        response['Cache-Control'] = 'no-cache'
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(['GET'])
def get_video_info_api(request):
    """API für Video-Informationen"""
    youtube_url = request.GET.get('url')
    
    if not youtube_url:
        return JsonResponse({'error': 'URL required'}, status=400)
    
    try:
        info = get_video_info(youtube_url)
        return JsonResponse(info)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

#### B) URL-Routing hinzufügen

In `rsl_tv/urls.py`:
```python
from tv import youtube_proxy

urlpatterns = [
    # ... existing patterns ...
    path('api/youtube-proxy/', youtube_proxy.proxy_youtube_video, name='youtube_proxy'),
    path('api/youtube-info/', youtube_proxy.get_video_info_api, name='youtube_info'),
]
```

#### C) Frontend: Custom Video Player

Erstelle `tv/templates/tv/live.html` neu:

```html
{% extends 'base.html' %}

{% block title %}LIVE – RSL TV{% endblock %}

{% block extra_css %}
<style>
    body {
        margin: 0;
        padding: 0;
        background: #000;
        overflow: hidden;
    }
    
    #tv-screen {
        width: 100vw;
        height: 100vh;
        position: relative;
        background: #000;
    }
    
    #video-player {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }
    
    #ad-break-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        display: none;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
        z-index: 1000;
    }
    
    #ad-break-overlay.active {
        display: flex;
    }
    
    .ad-logo {
        width: 200px;
        margin-bottom: 2rem;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    .ad-text {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    
    .ad-countdown {
        font-size: 3rem;
        font-weight: 700;
        color: #00acc1;
    }
    
    /* Versteckt alle Bedienelemente */
    video::-webkit-media-controls {
        display: none !important;
    }
    
    video::-webkit-media-controls-enclosure {
        display: none !important;
    }
</style>
{% endblock %}

{% block content %}
<div id="tv-screen">
    <video id="video-player" autoplay></video>
    
    <!-- Werbepausen-Overlay -->
    <div id="ad-break-overlay">
        <img src="{% static 'tv/img/logo-nobg.png' %}" alt="RSL TV" class="ad-logo">
        <div class="ad-text">Werbepause</div>
        <div class="ad-countdown" id="ad-countdown">--</div>
        <p style="margin-top: 2rem; opacity: 0.7;">Gleich geht's weiter...</p>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
class TVController {
    constructor() {
        this.player = document.getElementById('video-player');
        this.adOverlay = document.getElementById('ad-break-overlay');
        this.adCountdown = document.getElementById('ad-countdown');
        this.currentVideoUrl = null;
        this.pausePosition = 0;
        this.adDuration = 0;
        this.adTimer = null;
        
        this.init();
    }
    
    async init() {
        // Verhindere Bedienelemente
        this.player.controls = false;
        this.player.controlsList = 'nodownload nofullscreen noremoteplayback';
        this.player.disablePictureInPicture = true;
        
        // Verhindere Vorspulen via Tastatur
        document.addEventListener('keydown', (e) => {
            if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' '].includes(e.key)) {
                e.preventDefault();
            }
        });
        
        // Verhindere Rechtsklick
        this.player.addEventListener('contextmenu', (e) => e.preventDefault());
        
        // Starte Programm
        this.checkSchedule();
        
        // Regelmäßige Updates
        setInterval(() => this.checkSchedule(), 30000); // Alle 30 Sekunden
        setInterval(() => this.checkAdBreak(), 5000); // Alle 5 Sekunden
    }
    
    async checkSchedule() {
        try {
            const response = await fetch('/api/current-show/');
            const data = await response.json();
            
            if (data.current) {
                const videoUrl = data.current.video_url;
                
                // Neues Video?
                if (videoUrl !== this.currentVideoUrl) {
                    await this.loadVideo(videoUrl);
                }
            }
        } catch (error) {
            console.error('Fehler beim Laden des Programms:', error);
        }
    }
    
    async loadVideo(youtubeUrl) {
        try {
            // Hole Video über Proxy
            const proxyUrl = `/api/youtube-proxy/?url=${encodeURIComponent(youtubeUrl)}`;
            
            // Speichere aktuelle Position falls Video wechselt
            this.currentVideoUrl = youtubeUrl;
            
            // Lade Video
            this.player.src = proxyUrl;
            this.player.load();
            this.player.play();
            
            console.log('Video geladen:', youtubeUrl);
        } catch (error) {
            console.error('Fehler beim Laden des Videos:', error);
        }
    }
    
    async checkAdBreak() {
        try {
            const response = await fetch('/api/ad-break-status/');
            const data = await response.json();
            
            if (data.is_active) {
                this.startAdBreak(data.remaining_seconds);
            } else if (this.adOverlay.classList.contains('active')) {
                this.endAdBreak();
            }
        } catch (error) {
            console.error('Fehler beim Prüfen der Werbepause:', error);
        }
    }
    
    startAdBreak(duration) {
        if (!this.adOverlay.classList.contains('active')) {
            // Speichere Position
            this.pausePosition = this.player.currentTime;
            
            // Pause Video
            this.player.pause();
            
            // Zeige Overlay
            this.adOverlay.classList.add('active');
            
            console.log('Werbepause gestartet, Position gespeichert:', this.pausePosition);
        }
        
        // Update Countdown
        this.adCountdown.textContent = duration;
    }
    
    endAdBreak() {
        // Verstecke Overlay
        this.adOverlay.classList.remove('active');
        
        // Setze Video an exakter Position fort
        this.player.currentTime = this.pausePosition;
        this.player.play();
        
        console.log('Werbepause beendet, fortgesetzt bei:', this.pausePosition);
    }
}

// Starte Controller
const tv = new TVController();
</script>
{% endblock %}
```

#### D) API-Endpoints für Programm und Werbepausen

In `tv/views.py` hinzufügen:

```python
from django.http import JsonResponse
from django.utils import timezone
from tv.models import Schedule, LiveAdBreak

def api_current_show(request):
    """API: Aktuelle Sendung"""
    now = timezone.now()
    current = Schedule.objects.filter(
        start_time__lte=now,
        end_time__gte=now,
        is_active=True
    ).select_related('video').first()
    
    if current and current.video:
        return JsonResponse({
            'current': {
                'title': current.title,
                'video_url': current.video.video_url,
                'start_time': current.start_time.isoformat(),
                'end_time': current.end_time.isoformat(),
            }
        })
    
    return JsonResponse({'current': None})


def api_ad_break_status(request):
    """API: Werbepausen-Status"""
    # Prüfe ob aktive Werbepause läuft
    active_break = LiveAdBreak.objects.filter(
        is_active=True,
        ended_at__isnull=True
    ).first()
    
    if active_break:
        # Berechne verbleibende Zeit
        elapsed = (timezone.now() - active_break.started_at).total_seconds()
        remaining = max(0, active_break.max_duration - elapsed)
        
        return JsonResponse({
            'is_active': True,
            'remaining_seconds': int(remaining)
        })
    
    return JsonResponse({'is_active': False})
```

URLs hinzufügen:
```python
urlpatterns = [
    # ... existing ...
    path('api/current-show/', views.api_current_show, name='api_current_show'),
    path('api/ad-break-status/', views.api_ad_break_status, name='api_ad_break_status'),
]
```

#### E) Requirements erweitern

In `requirements.txt` hinzufügen:
```
yt-dlp==2024.3.10
```

---

## 🚀 Installation & Deployment

### 1. Dependencies installieren

```bash
pip install --break-system-packages yt-dlp==2024.3.10
```

### 2. FFmpeg prüfen

```bash
ffmpeg -version
# Sollte mindestens Version 4.x zeigen
```

### 3. Datenbank migrieren

```bash
python manage.py migrate
```

### 4. Stream-Keys setzen

```python
python manage.py shell

from tv.models import ProgramRoom

room = ProgramRoom.objects.first()

# YouTube
room.youtube_stream_key = "xxxx-xxxx-xxxx-xxxx"
room.youtube_rtmp_url = "rtmp://a.rtmp.youtube.com/live2"
room.is_streaming_youtube = True

# Twitch  
room.twitch_stream_key = "live_123456789_abcdefg"
room.twitch_rtmp_url = "rtmp://live.twitch.tv/app"
room.is_streaming_twitch = True

room.save()
exit()
```

### 5. Stream testen

```bash
# Stream starten
python python_streamer.py

# Logs beobachten
tail -f rsl_stream.log
```

### 6. Render.com Konfiguration

In Render.com Dashboard:

**Build Command:**
```bash
pip install --break-system-packages -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
```

**Start Command:**
```bash
gunicorn rsl_tv.wsgi:application & python python_streamer.py
```

**Environment Variables:**
- `YOUTUBE_STREAM_KEY`
- `TWITCH_STREAM_KEY`
- Alle anderen aus `.env.example`

---

## ✅ Checkliste

### Twitch Stream:
- [ ] Stream-Key korrekt (beginnt mit `live_`)
- [ ] RTMP URL: `rtmp://live.twitch.tv/app`
- [ ] Audio-Stream aktiviert
- [ ] FFmpeg läuft
- [ ] Firewall erlaubt Port 1935

### YouTube Stream:
- [ ] Stream-Key korrekt
- [ ] RTMP URL: `rtmp://a.rtmp.youtube.com/live2`
- [ ] YouTube Studio zeigt "Stream empfängt Daten"
- [ ] Latenz-Einstellung: Normal oder Niedrig

### Mediathek:
- [ ] Video-URLs in Datenbank korrekt
- [ ] YouTube-Nocookie Domain verwendet
- [ ] `get_stream_url()` gibt korrekte URLs zurück

### TV Display:
- [ ] `yt-dlp` installiert
- [ ] YouTube-Proxy funktioniert
- [ ] API-Endpoints erreichbar
- [ ] Werbepausen-System aktiviert

---

## 📝 Weitere Optimierungen

### Performance:
- Video-Caching für häufig gespielte Videos
- CDN für Media-Dateien
- Redis für Session-Management

### Monitoring:
- Stream-Uptime Tracking
- Error-Logging mit Sentry
- Viewer-Analytics

### Sicherheit:
- Rate-Limiting für Proxy
- CORS richtig konfigurieren
- Stream-Keys verschlüsseln

---

## 🆘 Support & Debugging

### Stream-Logs prüfen:
```bash
tail -f rsl_stream.log
tail -f stable_stream.log
```

### FFmpeg-Prozesse prüfen:
```bash
ps aux | grep ffmpeg
```

### Netzwerk-Test:
```bash
# YouTube
telnet a.rtmp.youtube.com 1935

# Twitch
telnet live.twitch.tv 1935
```

### Django-Shell Debugging:
```python
python manage.py shell

from tv.models import *
from python_streamer import *

# Teste Controller
controller = get_controller(program_room=ProgramRoom.objects.first())
controller.start()
```

---

**Viel Erfolg! 🚀📺**
