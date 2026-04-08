"""
Portable FFmpeg Downloader
Lädt FFmpeg automatisch herunter - KEINE Admin-Rechte nötig!
"""

import os
import sys
import urllib.request
import zipfile
import tarfile
import platform
from pathlib import Path

def download_ffmpeg():
    """Lädt portable FFmpeg herunter"""
    
    base_dir = Path(__file__).resolve().parent
    ffmpeg_dir = base_dir / 'ffmpeg'
    
    print("=" * 80)
    print("RSL TV - Portable FFmpeg Installer")
    print("=" * 80)
    print()
    
    # System erkennen
    system = platform.system()
    
    if system == 'Windows':
        url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
        filename = 'ffmpeg.zip'
        print(f"📥 Download FFmpeg für Windows...")
    elif system == 'Linux':
        url = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
        filename = 'ffmpeg.tar.xz'
        print(f"📥 Download FFmpeg für Linux...")
    else:
        print(f"❌ Unsupported OS: {system}")
        sys.exit(1)
    
    # Download
    download_path = base_dir / filename
    
    print(f"URL: {url}")
    print(f"Ziel: {download_path}")
    print()
    print("Downloading... (dies kann einige Minuten dauern)")
    
    try:
        urllib.request.urlretrieve(url, download_path)
        print("✅ Download abgeschlossen!")
    except Exception as e:
        print(f"❌ Download fehlgeschlagen: {e}")
        sys.exit(1)
    
    # Entpacken
    print()
    print("📦 Entpacke FFmpeg...")
    
    try:
        if system == 'Windows':
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(base_dir)
            
            # Finde entpackten Ordner
            for item in base_dir.glob('ffmpeg-*'):
                if item.is_dir():
                    item.rename(ffmpeg_dir)
                    break
        
        else:  # Linux
            with tarfile.open(download_path, 'r:xz') as tar_ref:
                tar_ref.extractall(base_dir)
            
            # Finde entpackten Ordner
            for item in base_dir.glob('ffmpeg-*'):
                if item.is_dir():
                    item.rename(ffmpeg_dir)
                    break
        
        print("✅ Entpacken abgeschlossen!")
        
    except Exception as e:
        print(f"❌ Entpacken fehlgeschlagen: {e}")
        sys.exit(1)
    
    # Cleanup
    try:
        download_path.unlink()
        print("✅ Temporäre Dateien gelöscht")
    except:
        pass
    
    # Prüfe FFmpeg
    if system == 'Windows':
        ffmpeg_exe = ffmpeg_dir / 'bin' / 'ffmpeg.exe'
    else:
        ffmpeg_exe = ffmpeg_dir / 'ffmpeg'
    
    if ffmpeg_exe.exists():
        print()
        print("=" * 80)
        print("✅ FFmpeg erfolgreich installiert!")
        print(f"📂 Pfad: {ffmpeg_exe}")
        print("=" * 80)
        print()
        print("Du kannst jetzt den Streamer starten:")
        print("  python python_streamer.py")
        print()
    else:
        print()
        print("❌ FFmpeg-Binary nicht gefunden!")
        print(f"Gesucht: {ffmpeg_exe}")

if __name__ == '__main__':
    download_ffmpeg()