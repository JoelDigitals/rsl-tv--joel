#!/usr/bin/env python3
"""
RSL TV – Minimaler Python Streamer (OHNE FFmpeg, OHNE PyAV)
===========================================================
Nur mit: opencv-python, numpy, pillow

Nutzt OpenCV's VideoWriter mit RAW-Format und
piped die Daten direkt via subprocess zu einem
externen RTMP-Tool (z.B. stunnel oder streamlink)

ODER: Nutzt HTTP-Live-Streaming für einfaches Testen

Abhängigkeiten:
    pip install opencv-python numpy pillow requests python-dotenv django
"""

import os
import sys
import time
import logging
import threading
import subprocess
import socket
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Django Setup
if __name__ == '__main__':
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rsl_tv.settings')
    django.setup()

import cv2
import numpy as np
from PIL import Image

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rsl_stream.log')
    ],
)
log = logging.getLogger('RSL-TV-Simple')


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO SOURCE (vereinfacht)
# ══════════════════════════════════════════════════════════════════════════════

class SimpleVideoSource:
    """Einfache Video-Quelle"""
    
    def __init__(self, source_type='image', source_path=None, width=1920, height=1080):
        self.width = width
        self.height = height
        self.source_type = source_type
        self.source_path = source_path
        self.cap = None
        self.static_frame = None
        
        self._init_source()
    
    def _init_source(self):
        """Initialisiert Quelle"""
        if self.source_type == 'image':
            self._load_image()
        elif self.source_type == 'webcam':
            self._open_webcam()
        elif self.source_type == 'url':
            self._open_url()
        else:
            self._create_default_frame()
    
    def _load_image(self):
        """Lädt statisches Bild"""
        if self.source_path and Path(self.source_path).exists():
            img = cv2.imread(str(self.source_path))
            if img is not None:
                self.static_frame = cv2.resize(img, (self.width, self.height))
                log.info(f"🖼️  Bild geladen: {self.source_path}")
                return
        
        self._create_default_frame()
    
    def _open_webcam(self):
        """Öffnet Webcam"""
        device_id = 0
        if self.source_path and self.source_path.isdigit():
            device_id = int(self.source_path)
        
        self.cap = cv2.VideoCapture(device_id)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            log.info(f"📹 Webcam {device_id} geöffnet")
        else:
            log.warning(f"Webcam {device_id} nicht verfügbar")
            self._create_default_frame()
    
    def _open_url(self):
        """Öffnet Video-URL"""
        if not self.source_path:
            self._create_default_frame()
            return
        
        self.cap = cv2.VideoCapture(self.source_path)
        if self.cap.isOpened():
            log.info(f"🌐 URL-Stream geöffnet: {self.source_path}")
        else:
            log.error(f"URL konnte nicht geöffnet werden: {self.source_path}")
            self._create_default_frame()
    
    def _create_default_frame(self):
        """Erstellt Standard-Frame"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Gradient-Hintergrund
        for y in range(self.height):
            intensity = int(30 + (y / self.height) * 50)
            frame[y, :] = [intensity, intensity, intensity]
        
        # RSL TV Logo
        cv2.putText(frame, 'RSL TV', 
                   (self.width // 2 - 300, self.height // 2 - 50),
                   cv2.FONT_HERSHEY_BOLD, 5, (255, 255, 255), 5)
        
        cv2.putText(frame, 'LIVE', 
                   (self.width // 2 - 100, self.height // 2 + 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
        
        self.static_frame = frame
        log.info("📺 Standard-Frame erstellt")
    
    def get_frame(self):
        """Gibt aktuelles Frame zurück"""
        if self.static_frame is not None:
            return self.static_frame.copy()
        
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))
                return frame
        
        # Fallback
        return self._create_error_frame()
    
    def _create_error_frame(self):
        """Erstellt Error-Frame"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.putText(frame, 'SIGNAL LOST', 
                   (self.width // 2 - 300, self.height // 2),
                   cv2.FONT_HERSHEY_BOLD, 3, (0, 0, 255), 3)
        return frame
    
    def release(self):
        """Cleanup"""
        if self.cap:
            self.cap.release()


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITOR
# ══════════════════════════════════════════════════════════════════════════════

class SimpleCompositor:
    """Einfacher Video-Compositor"""
    
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.logo = None
        self.logo_pos = (0, 0)
    
    def load_logo(self, logo_path, position='top_right', scale=80):
        """Lädt Logo"""
        try:
            # Mit PIL laden (RGBA Support)
            pil_img = Image.open(logo_path).convert('RGBA')
            
            # Skalieren
            aspect = pil_img.height / pil_img.width
            w = scale
            h = int(scale * aspect)
            pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
            
            # Zu numpy (BGRA für OpenCV)
            logo_rgba = np.array(pil_img)
            logo_bgr = cv2.cvtColor(logo_rgba, cv2.COLOR_RGBA2BGRA)
            
            self.logo = logo_bgr
            
            # Position
            padding = 10
            if position == 'top_right':
                self.logo_pos = (self.width - w - padding, padding)
            elif position == 'top_left':
                self.logo_pos = (padding, padding)
            elif position == 'bottom_right':
                self.logo_pos = (self.width - w - padding, self.height - h - padding)
            else:  # bottom_left
                self.logo_pos = (padding, self.height - h - padding)
            
            log.info(f"✅ Logo geladen: {w}x{h}px")
            
        except Exception as e:
            log.error(f"Logo-Fehler: {e}")
    
    def overlay_logo(self, frame):
        """Fügt Logo hinzu"""
        if self.logo is None:
            return frame
        
        x, y = self.logo_pos
        h, w = self.logo.shape[:2]
        
        # Sicherstellen dass Logo ins Frame passt
        if y + h > frame.shape[0] or x + w > frame.shape[1]:
            return frame
        
        # Alpha-Blending (vereinfacht)
        roi = frame[y:y+h, x:x+w]
        
        # Logo hat Alpha-Channel
        alpha = self.logo[:, :, 3] / 255.0
        
        for c in range(3):
            roi[:, :, c] = alpha * self.logo[:, :, c] + (1 - alpha) * roi[:, :, c]
        
        frame[y:y+h, x:x+w] = roi
        
        return frame
    
    def add_text(self, frame, text, position='bottom'):
        """Fügt Text hinzu"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.0
        thickness = 2
        color = (255, 255, 255)
        
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        
        if position == 'bottom':
            x = (self.width - tw) // 2
            y = self.height - 30
        else:
            x = (self.width - tw) // 2
            y = 50
        
        # Hintergrund
        cv2.rectangle(frame, (x - 5, y - th - 5), (x + tw + 5, y + 5), (0, 0, 0), -1)
        
        # Text
        cv2.putText(frame, text, (x, y), font, scale, color, thickness)
        
        return frame
    
    def compose(self, source_frame, text=None):
        """Komponiert Frame"""
        frame = source_frame.copy()
        frame = self.overlay_logo(frame)
        
        if text:
            frame = self.add_text(frame, text)
        
        return frame


# ══════════════════════════════════════════════════════════════════════════════
# STREAMER mit GStreamer-Pipe (Alternative zu PyAV)
# ══════════════════════════════════════════════════════════════════════════════

class GStreamerStreamer:
    """
    Streamt via GStreamer (falls installiert)
    Fallback: Speichert zu lokalem File
    """
    
    def __init__(self, rtmp_url, width=1920, height=1080, fps=30):
        self.rtmp_url = rtmp_url
        self.width = width
        self.height = height
        self.fps = fps
        self.process = None
        self.is_active = False
        
        self._init_stream()
    
    def _init_stream(self):
        """Initialisiert Stream"""
        # Prüfe ob gst-launch-1.0 verfügbar ist
        import shutil
        if shutil.which('gst-launch-1.0'):
            self._init_gstreamer()
        else:
            log.warning("GStreamer nicht gefunden, verwende File-Output")
            self._init_file_output()
    
    def _init_gstreamer(self):
        """Initialisiert GStreamer Pipeline"""
        try:
            # GStreamer Pipeline für RTMP
            pipeline = [
                'gst-launch-1.0',
                '-e',
                'fdsrc',
                '!',
                f'videoparse width={self.width} height={self.height} format=bgr framerate={self.fps}/1',
                '!',
                'videoconvert',
                '!',
                'x264enc tune=zerolatency bitrate=4000 speed-preset=veryfast',
                '!',
                'flvmux',
                '!',
                f'rtmpsink location={self.rtmp_url}'
            ]
            
            self.process = subprocess.Popen(
                pipeline,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.is_active = True
            log.info("✅ GStreamer-Pipeline gestartet")
            
        except Exception as e:
            log.error(f"GStreamer-Fehler: {e}")
            self._init_file_output()
    
    def _init_file_output(self):
        """Fallback: Output zu File"""
        output_file = 'output_stream.avi'
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.writer = cv2.VideoWriter(output_file, fourcc, self.fps, (self.width, self.height))
        
        if self.writer.isOpened():
            self.is_active = True
            log.info(f"📁 File-Output: {output_file}")
        else:
            log.error("File-Output konnte nicht geöffnet werden")
            self.is_active = False
    
    def send_frame(self, frame):
        """Sendet Frame"""
        if not self.is_active:
            return False
        
        try:
            if self.process:
                # GStreamer pipe
                self.process.stdin.write(frame.tobytes())
                return True
            elif hasattr(self, 'writer'):
                # File writer
                self.writer.write(frame)
                return True
        except Exception as e:
            log.error(f"Frame-Send-Fehler: {e}")
            return False
        
        return False
    
    def close(self):
        """Schließt Streamer"""
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
        
        if hasattr(self, 'writer'):
            self.writer.release()
        
        self.is_active = False


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLE STREAM CONTROLLER
# ══════════════════════════════════════════════════════════════════════════════

class SimpleStreamController:
    """Vereinfachter Stream-Controller"""
    
    def __init__(self, director_room):
        self.director_room = director_room
        self.width = 1920
        self.height = 1080
        self.fps = 30
        
        self.source = None
        self.compositor = SimpleCompositor(self.width, self.height)
        self.streamers = []
        
        self.is_running = False
        self.thread = None
    
    def setup(self):
        """Setup"""
        # Video Source
        active_camera = self.director_room.active_camera
        
        if not active_camera:
            log.warning("Keine Kamera, verwende Pausenbild")
            pause_path = 'media/pause.jpg'
            self.source = SimpleVideoSource('image', pause_path, self.width, self.height)
        else:
            if active_camera.camera_type == 'webcam':
                device = active_camera.source_url if active_camera.source_url else '0'
                self.source = SimpleVideoSource('webcam', device, self.width, self.height)
            elif active_camera.camera_type == 'url':
                self.source = SimpleVideoSource('url', active_camera.source_url, self.width, self.height)
            else:
                image_path = active_camera.source_file.path if active_camera.source_file else None
                self.source = SimpleVideoSource('image', image_path, self.width, self.height)
        
        # Logo
        try:
            from tv.models import SenderLogo
            logo = SenderLogo.objects.filter(is_active=True).first()
            if logo and logo.logo:
                self.compositor.load_logo(logo.logo.path, logo.position, logo.scale)
        except Exception as e:
            log.error(f"Logo-Fehler: {e}")
        
        # Streamers
        if self.director_room.is_streaming_youtube:
            key = os.environ.get('YOUTUBE_STREAM_KEY', '')
            if key:
                url = f"rtmp://a.rtmp.youtube.com/live2/{key}"
                streamer = GStreamerStreamer(url, self.width, self.height, self.fps)
                if streamer.is_active:
                    self.streamers.append(('YouTube', streamer))
        
        if self.director_room.is_streaming_twitch:
            key = os.environ.get('TWITCH_STREAM_KEY', '')
            if key:
                url = f"rtmp://live.twitch.tv/app/{key}"
                streamer = GStreamerStreamer(url, self.width, self.height, self.fps)
                if streamer.is_active:
                    self.streamers.append(('Twitch', streamer))
        
        return len(self.streamers) > 0 or hasattr(self, 'source')
    
    def start(self):
        """Startet Stream"""
        if self.is_running:
            log.warning("Stream läuft bereits")
            return False
        
        log.info("═══════════════════════════════════════════════════════")
        log.info("🎬 Simple Python Streamer startet...")
        log.info("═══════════════════════════════════════════════════════")
        
        if not self.setup():
            log.error("❌ Setup fehlgeschlagen")
            return False
        
        self.is_running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        
        log.info("✅ Stream läuft!")
        return True
    
    def _loop(self):
        """Haupt-Loop"""
        frame_time = 1.0 / self.fps
        frame_count = 0
        
        try:
            while self.is_running:
                start = time.time()
                
                # Frame holen
                frame = self.source.get_frame()
                
                # Komponieren
                timestamp = datetime.now().strftime("%H:%M:%S")
                composed = self.compositor.compose(frame, text=f"RSL TV • {timestamp}")
                
                # Senden
                for name, streamer in self.streamers:
                    streamer.send_frame(composed)
                
                frame_count += 1
                
                if frame_count % (self.fps * 10) == 0:
                    log.info(f"📊 {frame_count} Frames gesendet")
                
                # Timing
                elapsed = time.time() - start
                sleep = max(0, frame_time - elapsed)
                if sleep > 0:
                    time.sleep(sleep)
                
        except Exception as e:
            log.error(f"Loop-Fehler: {e}")
        finally:
            self._cleanup()
    
    def stop(self):
        """Stoppt Stream"""
        log.info("⏹️  Stoppe Stream...")
        self.is_running = False
        
        if self.thread:
            self.thread.join(timeout=5)
    
    def _cleanup(self):
        """Cleanup"""
        for name, streamer in self.streamers:
            streamer.close()
            log.info(f"✅ {name} geschlossen")
        
        if self.source:
            self.source.release()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Main"""
    from tv.models import DirectorRoom
    
    log.info("╔═══════════════════════════════════════════════════════╗")
    log.info("║    RSL TV – Simple Python Streamer                   ║")
    log.info("║    Kein FFmpeg! Kein PyAV!                            ║")
    log.info("╚═══════════════════════════════════════════════════════╝")
    
    try:
        director_room = DirectorRoom.objects.first()
        if not director_room:
            log.error("❌ Kein Regieraum gefunden!")
            sys.exit(1)
    except Exception as e:
        log.error(f"❌ Fehler: {e}")
        sys.exit(1)
    
    log.info(f"🎬 Regieraum: {director_room.name}")
    
    controller = SimpleStreamController(director_room)
    
    auto_start = os.environ.get('AUTO_START_STREAM', 'false').lower() == 'true'
    if auto_start:
        controller.start()
    
    try:
        log.info("\n🎯 Läuft... (Ctrl+C zum Beenden)\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\n⏹️  Beende...")
        controller.stop()
        log.info("👋 Tschüss!")


if __name__ == '__main__':
    main()