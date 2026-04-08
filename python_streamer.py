"""
RSL TV Python Streamer v13.1 - DEBUG VERSION
═══════════════════════════════════════════════════════════════════════════════
Mit detailliertem Logging und Fehlerbehandlung
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import logging
import subprocess
import threading
import platform
from datetime import datetime, timedelta
from pathlib import Path

# Django Setup
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rsl_tv.settings')

import django
django.setup()

from django.utils import timezone
from tv.models import (
    ProgramRoom, Schedule, StandbyImage, AdVideo, 
    VideoCache, Video
)

import cv2
import numpy as np

# Logging
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG statt INFO
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('rsl_stream.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RSL')


def find_ffmpeg():
    """Findet FFmpeg (portable oder System)"""
    
    # 1. Portable FFmpeg im Projektordner
    if platform.system() == 'Windows':
        portable_paths = [
            BASE_DIR / 'ffmpeg' / 'bin' / 'ffmpeg.exe',
            BASE_DIR / 'ffmpeg' / 'ffmpeg.exe',
            Path('C:/ffmpeg/bin/ffmpeg.exe'),
        ]
    else:
        portable_paths = [
            BASE_DIR / 'ffmpeg' / 'ffmpeg',
            BASE_DIR / 'bin' / 'ffmpeg',
            Path.home() / 'bin' / 'ffmpeg',
        ]
    
    for path in portable_paths:
        if path.exists():
            logger.info(f"✅ Portable FFmpeg gefunden: {path}")
            return str(path)
    
    # 2. System FFmpeg
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=3
        )
        if result.returncode == 0:
            logger.info("✅ System FFmpeg gefunden")
            return 'ffmpeg'
    except:
        pass
    
    logger.error("❌ FFmpeg nicht gefunden!")
    return None


class StreamController:
    """Haupt-Controller mit FFmpeg + Debugging"""
    
    def __init__(self, program_room=None):
        self.program_room = program_room or ProgramRoom.objects.first()
        self.is_running = False
        self.threads = []
        
        # Video-Settings
        self.width = 1280
        self.height = 720
        self.fps = 25
        
        # FFmpeg-Prozesse
        self.processes = []
        
        # FFmpeg finden
        self.ffmpeg_path = find_ffmpeg()
        
        # Frame-Statistik
        self.frame_stats = {}
        
        logger.info("StreamController v13.1 initialisiert")
    
    def start(self):
        """Startet Stream"""
        if self.is_running:
            logger.warning("Stream läuft bereits!")
            return False
        
        if not self.ffmpeg_path:
            logger.error("FFmpeg nicht gefunden!")
            return False
        
        self.is_running = True
        
        # Starte FFmpeg-Prozesse
        room = self.program_room
        
        if room.is_streaming_youtube and room.youtube_stream_key:
            self._start_stream(
                f"{room.youtube_rtmp_url}/{room.youtube_stream_key}",
                "YouTube"
            )
        
        if room.is_streaming_twitch and room.twitch_stream_key:
            self._start_stream(
                f"{room.twitch_rtmp_url}/{room.twitch_stream_key}",
                "Twitch"
            )
        
        if not self.processes:
            logger.error("Keine Streaming-Ziele konfiguriert!")
            self.is_running = False
            return False
        
        logger.info("✅ Stream gestartet")
        return True
    
    def _start_stream(self, rtmp_url, name):
        """Startet einen Stream mit Debugging"""
        
        # WICHTIG: Audio hinzufügen (YouTube/Twitch brauchen Audio!)
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.fps),
            '-i', '-',  # Video von stdin
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=stereo',  # Silent Audio
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'zerolatency',
            '-b:v', '2500k',
            '-maxrate', '2500k',
            '-bufsize', '5000k',
            '-pix_fmt', 'yuv420p',
            '-g', str(self.fps * 2),
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-shortest',  # Stoppe wenn Video endet
            '-f', 'flv',
            rtmp_url
        ]
        
        logger.debug(f"{name} FFmpeg Command: {' '.join(cmd)}")
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes.append({
                'process': proc,
                'name': name
            })
            
            # Statistik initialisieren
            self.frame_stats[name] = {
                'frames_sent': 0,
                'errors': 0,
                'last_frame_time': time.time()
            }
            
            # Frame-Thread starten
            thread = threading.Thread(
                target=self._stream_frames,
                args=(proc, name),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
            
            # FFmpeg-Fehlerausgabe überwachen
            error_thread = threading.Thread(
                target=self._monitor_ffmpeg_errors,
                args=(proc, name),
                daemon=True
            )
            error_thread.start()
            self.threads.append(error_thread)
            
            logger.info(f"📡 {name} Stream gestartet")
            
        except Exception as e:
            logger.error(f"{name} Stream-Start Fehler: {e}")
    
    def _monitor_ffmpeg_errors(self, proc, name):
        """Überwacht FFmpeg stderr für Fehler"""
        try:
            for line in proc.stderr:
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    if 'error' in line_str.lower() or 'failed' in line_str.lower():
                        logger.error(f"{name} FFmpeg ERROR: {line_str}")
                    else:
                        logger.debug(f"{name} FFmpeg: {line_str}")
        except:
            pass
    
    def _stream_frames(self, proc, name):
        """Sendet Frames an FFmpeg"""
        frame_count = 0
        last_log = time.time()
        
        logger.info(f"{name}: Frame-Thread gestartet")
        
        while self.is_running and proc.poll() is None:
            try:
                # Frame holen
                frame = self._get_current_frame()
                
                if frame is None:
                    logger.warning(f"{name}: Kein Frame - nutze Default")
                    frame = self._create_default_frame()
                
                # Frame-Größe prüfen
                expected_size = self.width * self.height * 3
                actual_size = frame.size
                
                if actual_size != expected_size:
                    logger.error(f"{name}: Frame-Größe falsch! Erwartet: {expected_size}, Ist: {actual_size}")
                    frame = self._create_default_frame()
                
                # An FFmpeg senden
                try:
                    proc.stdin.write(frame.tobytes())
                    proc.stdin.flush()  # WICHTIG: Buffer leeren!
                except BrokenPipeError:
                    logger.error(f"{name}: FFmpeg Pipe geschlossen (BrokenPipeError)")
                    break
                except Exception as e:
                    logger.error(f"{name}: Pipe-Write Fehler: {e}")
                    self.frame_stats[name]['errors'] += 1
                    break
                
                # Statistik
                frame_count += 1
                self.frame_stats[name]['frames_sent'] = frame_count
                self.frame_stats[name]['last_frame_time'] = time.time()
                
                # Log alle 5 Sekunden
                if time.time() - last_log > 5:
                    logger.info(f"{name}: {frame_count} Frames gesendet ({frame_count / (time.time() - last_log + 0.1):.1f} FPS)")
                    last_log = time.time()
                
                # FPS-Timing
                time.sleep(1.0 / self.fps)
                
            except Exception as e:
                logger.error(f"{name} Frame-Fehler: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(0.1)
        
        logger.info(f"{name}: Frame-Thread beendet ({frame_count} frames)")
        
        # FFmpeg-Exit-Code prüfen
        exit_code = proc.poll()
        if exit_code is not None and exit_code != 0:
            logger.error(f"{name}: FFmpeg beendet mit Exit-Code {exit_code}")
    
    def stop(self):
        """Stoppt Stream"""
        logger.info("Stoppe Stream...")
        self.is_running = False
        
        # Frame-Statistik ausgeben
        for name, stats in self.frame_stats.items():
            logger.info(f"{name} Statistik: {stats['frames_sent']} Frames, {stats['errors']} Fehler")
        
        # Warte auf Threads
        for thread in self.threads:
            thread.join(timeout=3)
        
        # Stoppe FFmpeg
        for proc_info in self.processes:
            try:
                proc = proc_info['process']
                proc.stdin.close()
                proc.wait(timeout=3)
            except:
                try:
                    proc.kill()
                except:
                    pass
        
        self.processes.clear()
        self.threads.clear()
        
        logger.info("⏹ Stream gestoppt")
    
    def _get_current_frame(self):
        """Frame basierend auf Programm holen"""
        room = self.program_room
        
        try:
            room.refresh_from_db()
        except:
            logger.warning("DB-Refresh fehlgeschlagen")
        
        now = timezone.now()
        
        # Werbepause?
        if room.ad_break_active:
            return self._get_standby_frame()
        
        # Sendung?
        current_show = Schedule.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            is_active=True
        ).first()
        
        if current_show and current_show.video:
            frame = self._get_video_frame(current_show, now)
            if frame is not None:
                return frame
        
        return self._get_standby_frame()
    
    def _get_video_frame(self, show, now):
        """Video-Frame"""
        video = show.video
        elapsed = int((now - show.start_time).total_seconds())
        
        # Video-Quelle
        video_path = None
        cache = getattr(video, 'cache', None)
        
        if cache and cache.is_ready():
            video_path = cache.local_path
        elif video.video_file:
            video_path = video.video_file.path
        elif video.source_url:
            video_path = video.source_url
        
        if not video_path:
            logger.debug(f"Kein Video-Pfad für: {show.title}")
            return None
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                logger.error(f"Konnte Video nicht öffnen: {video_path}")
                return None
            
            cap.set(cv2.CAP_PROP_POS_MSEC, elapsed * 1000)
            
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return cv2.resize(frame, (self.width, self.height))
            else:
                logger.warning(f"Konnte Frame nicht lesen aus: {video_path}")
                
        except Exception as e:
            logger.error(f"Video-Frame Fehler: {e}")
        
        return None
    
    def _get_standby_frame(self):
        """Pausenbild"""
        standby = StandbyImage.objects.filter(is_active=True).first()
        
        if standby and standby.image:
            try:
                img = cv2.imread(standby.image.path)
                if img is not None:
                    return cv2.resize(img, (self.width, self.height))
            except Exception as e:
                logger.error(f"Standby-Bild Fehler: {e}")
        
        return self._create_default_frame()
    
    def _create_default_frame(self):
        """Default Pausenbild"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Gradient
        for i in range(self.height):
            color = int(30 + (i / self.height) * 20)
            frame[i, :] = [color, color, color]
        
        # Text
        cv2.putText(
            frame, "RSL TV",
            (self.width // 2 - 200, self.height // 2 - 30),
            cv2.FONT_HERSHEY_BOLD, 2.5, (255, 255, 255), 4, cv2.LINE_AA
        )
        
        cv2.putText(
            frame, "Kurze Pause",
            (self.width // 2 - 150, self.height // 2 + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (200, 200, 200), 2, cv2.LINE_AA
        )
        
        return frame


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL
# ═══════════════════════════════════════════════════════════════════════════

_stream_controller = None

def get_stream_controller(program_room=None, director_room=None):
    global _stream_controller
    if _stream_controller is None:
        _stream_controller = StreamController(program_room=program_room)
    return _stream_controller

def reset_stream_controller():
    global _stream_controller
    if _stream_controller:
        _stream_controller.stop()
    _stream_controller = None


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("RSL TV Streamer v13.1 - DEBUG VERSION")
    logger.info("=" * 80)
    
    room = ProgramRoom.objects.first()
    if not room:
        logger.error("Kein ProgramRoom!")
        sys.exit(1)
    
    controller = get_stream_controller(program_room=room)
    
    try:
        if controller.start():
            logger.info("Stream läuft... (Ctrl+C zum Beenden)")
            
            while controller.is_running:
                time.sleep(1)
        else:
            logger.error("Stream konnte nicht gestartet werden!")
    
    except KeyboardInterrupt:
        logger.info("Stoppe...")
    finally:
        controller.stop()
        logger.info("Beendet.")