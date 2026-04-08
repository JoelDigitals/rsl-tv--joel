#!/usr/bin/env python3
"""
RSL TV - System-Test Script
============================
Prüft alle Komponenten und Konfigurationen
"""

import sys
import os
import subprocess
import importlib.util

# Farben
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def check_package(package_name, import_name=None):
    """Prüft ob ein Python-Paket installiert ist"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False

def check_command(command):
    """Prüft ob ein Shell-Kommando verfügbar ist"""
    try:
        subprocess.run([command, '--version'], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def get_version(command):
    """Holt Version eines Kommandos"""
    try:
        result = subprocess.run([command, '--version'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              text=True)
        return result.stdout.split('\n')[0]
    except:
        return "Unbekannt"

print("=" * 60)
print("  RSL TV - System-Test")
print("=" * 60)
print()

# Test 1: Python-Version
print("Test 1: Python-Version")
python_version = sys.version.split()[0]
if sys.version_info >= (3, 8):
    print_success(f"Python {python_version}")
else:
    print_error(f"Python {python_version} - Mindestens 3.8 erforderlich!")
print()

# Test 2: Notwendige Pakete
print("Test 2: Python-Pakete")
packages = {
    'opencv-python': 'cv2',
    'numpy': 'numpy',
    'django': 'django',
    'python-dotenv': 'dotenv',
    'yt-dlp': 'yt_dlp'
}

for package, import_name in packages.items():
    if check_package(package, import_name):
        print_success(f"{package}")
    else:
        print_error(f"{package} nicht installiert!")
        print_info(f"  Installiere mit: pip install --break-system-packages {package}")
print()

# Test 3: System-Kommandos
print("Test 3: System-Kommandos")
commands = ['ffmpeg', 'python3']

for cmd in commands:
    if check_command(cmd):
        version = get_version(cmd)
        print_success(f"{cmd}: {version}")
    else:
        print_error(f"{cmd} nicht gefunden!")
        if cmd == 'ffmpeg':
            print_info("  Ubuntu/Debian: sudo apt install ffmpeg")
            print_info("  MacOS: brew install ffmpeg")
print()

# Test 4: Django Setup
print("Test 4: Django Setup")
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rsl_tv.settings')
    import django
    django.setup()
    print_success("Django konfiguriert")
    
    # Prüfe Models
    from tv.models import ProgramRoom, DirectorRoom
    
    program_room = ProgramRoom.objects.first()
    director_room = DirectorRoom.objects.first()
    
    if program_room or director_room:
        print_success("Room-Konfiguration gefunden")
    else:
        print_warning("Keine Room-Konfiguration in Datenbank!")
        print_info("  Erstelle ProgramRoom oder DirectorRoom")
    
except Exception as e:
    print_error(f"Django-Fehler: {e}")
print()

# Test 5: Stream-Konfiguration
print("Test 5: Stream-Konfiguration")
try:
    from tv.models import ProgramRoom, DirectorRoom
    
    room = ProgramRoom.objects.first() or DirectorRoom.objects.first()
    
    if room:
        # YouTube
        if room.is_streaming_youtube:
            if room.youtube_stream_key:
                print_success(f"YouTube: Aktiviert (Key: {room.youtube_stream_key[:10]}...)")
            else:
                print_error("YouTube: Aktiviert aber kein Stream-Key!")
        else:
            print_warning("YouTube: Deaktiviert")
        
        # Twitch
        if room.is_streaming_twitch:
            if room.twitch_stream_key:
                print_success(f"Twitch: Aktiviert (Key: {room.twitch_stream_key[:10]}...)")
            else:
                print_error("Twitch: Aktiviert aber kein Stream-Key!")
        else:
            print_warning("Twitch: Deaktiviert")
        
        # RTMP URLs
        if hasattr(room, 'youtube_rtmp_url'):
            print_info(f"  YouTube RTMP: {room.youtube_rtmp_url}")
        if hasattr(room, 'twitch_rtmp_url'):
            print_info(f"  Twitch RTMP: {room.twitch_rtmp_url}")
    else:
        print_error("Keine Room-Konfiguration!")
        
except Exception as e:
    print_error(f"Fehler: {e}")
print()

# Test 6: Dateien
print("Test 6: Wichtige Dateien")
files = [
    'python_streamer.py',
    'tv/templates/tv/mediathek.html',
    'tv/templates/tv/tv_display.html',
    'tv/api_views.py',
    'manage.py'
]

for file in files:
    if os.path.exists(file):
        print_success(file)
    else:
        print_error(f"{file} nicht gefunden!")
print()

# Test 7: API-Endpoints (wenn Server läuft)
print("Test 7: API-Endpoints")
try:
    import requests
    
    endpoints = [
        'http://localhost:8000/api/current-show/',
        'http://localhost:8000/api/ad-break-status/',
        'http://localhost:8000/api/youtube-stream/?video_id=dQw4w9WgXcQ'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=2)
            if response.status_code == 200:
                print_success(f"{endpoint}")
            else:
                print_warning(f"{endpoint} - Status {response.status_code}")
        except requests.exceptions.ConnectionError:
            print_warning(f"{endpoint} - Server nicht erreichbar")
            print_info("  Starte Server mit: python manage.py runserver")
        except Exception as e:
            print_error(f"{endpoint} - {e}")
            
except ImportError:
    print_warning("requests nicht installiert - API-Tests übersprungen")
    print_info("  Installiere mit: pip install requests")
print()

# Test 8: Netzwerk (RTMP-Ports)
print("Test 8: Netzwerk-Konnektivität")
import socket

rtmp_servers = [
    ('live.twitch.tv', 1935, 'Twitch'),
    ('a.rtmp.youtube.com', 1935, 'YouTube')
]

for host, port, name in rtmp_servers:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print_success(f"{name} ({host}:{port}) erreichbar")
        else:
            print_error(f"{name} ({host}:{port}) nicht erreichbar!")
    except Exception as e:
        print_error(f"{name} - {e}")
print()

# Zusammenfassung
print("=" * 60)
print("  Test abgeschlossen!")
print("=" * 60)
print()
print("Nächste Schritte:")
print()
print("Falls Fehler aufgetreten sind:")
print("1. Installiere fehlende Pakete")
print("2. Konfiguriere Stream-Keys in der Datenbank")
print("3. Starte Django-Server: python manage.py runserver")
print("4. Teste Stream: python python_streamer.py")
print()
print("Siehe KOMPLETTE_LOESUNGSANLEITUNG.md für Details")
print()
