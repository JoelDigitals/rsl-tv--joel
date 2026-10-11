"""
YouTube Import - ULTIMATE VERSION
Importiert JEDE YouTube URL - auch VL-Playlists!
"""

import re
import requests
import json
from django.utils import timezone


def extract_all_video_urls_from_page(url):
    """
    Extrahiert ALLE Video-URLs von einer beliebigen YouTube-Seite
    Funktioniert mit: Playlists, Channels, Suchen, Mix, ALLES!
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'de-DE,de;q=0.9',
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            return []
        
        html = response.text
        
        # METHODE 1: Finde alle /watch?v= Links
        video_ids = set()
        
        # Pattern für Video-IDs
        patterns = [
            r'/watch\?v=([a-zA-Z0-9_-]{11})',
            r'"videoId":"([a-zA-Z0-9_-]{11})"',
            r'video_id=([a-zA-Z0-9_-]{11})',
            r'/embed/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html)
            video_ids.update(matches)
        
        # METHODE 2: Extrahiere aus JSON (wenn vorhanden)
        try:
            # Suche ytInitialData
            match = re.search(r'var ytInitialData = ({.+?});', html)
            if match:
                data = json.loads(match.group(1))
                # Durchsuche rekursiv nach videoId
                video_ids.update(find_video_ids_in_json(data))
        except:
            pass
        
        return list(video_ids)
        
    except Exception as e:
        print(f"Fehler beim Laden: {e}")
        return []


def find_video_ids_in_json(obj, video_ids=None):
    """Rekursiv durch JSON nach videoId suchen"""
    if video_ids is None:
        video_ids = set()
    
    if isinstance(obj, dict):
        if 'videoId' in obj and isinstance(obj['videoId'], str) and len(obj['videoId']) == 11:
            video_ids.add(obj['videoId'])
        for value in obj.values():
            find_video_ids_in_json(value, video_ids)
    elif isinstance(obj, list):
        for item in obj:
            find_video_ids_in_json(item, video_ids)
    
    return video_ids


def get_video_info_oembed(video_id):
    """Holt Video-Infos über oEmbed"""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'title': data.get('title', f'Video {video_id}'),
                'thumbnail': data.get('thumbnail_url', f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'),
                'author': data.get('author_name', ''),
            }
    except:
        pass
    
    return {
        'title': f'Video {video_id}',
        'thumbnail': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
        'author': '',
    }


def import_from_any_youtube_url(url_input):
    """
    UNIVERSAL IMPORT
    Akzeptiert JEDE YouTube URL:
    - Playlists (PL, UU, FL, LL, VL, RD, etc.)
    - Channel-Seiten
    - Video-URLs mit Playlists
    - "Später ansehen"
    - Mix
    - Alles!
    
    Returns: Liste von Video-Daten
    """
    
    # Normalisiere URL
    url = url_input.strip()
    
    # Wenn es nur eine Video-URL ist (kein list Parameter)
    # dann mache daraus eine Ein-Video-Liste
    if '/watch?v=' in url and 'list=' not in url:
        video_id = url.split('watch?v=')[1].split('&')[0]
        info = get_video_info_oembed(video_id)
        return [{
            'video_id': video_id,
            'title': info['title'],
            'thumbnail': info['thumbnail'],
            'url': f'https://www.youtube.com/watch?v={video_id}'
        }]
    
    # Für ALLES andere: Extrahiere alle Videos von der Seite
    print(f"Lade Seite: {url}")
    video_ids = extract_all_video_urls_from_page(url)
    
    if not video_ids:
        print("Keine Video-IDs gefunden")
        return []
    
    print(f"Gefundene Video-IDs: {len(video_ids)}")
    
    # Hole Infos für jedes Video
    videos = []
    for video_id in video_ids[:100]:  # Max 100 Videos
        try:
            info = get_video_info_oembed(video_id)
            videos.append({
                'video_id': video_id,
                'title': info['title'],
                'thumbnail': info['thumbnail'],
                'url': f'https://www.youtube.com/watch?v={video_id}'
            })
        except Exception as e:
            print(f"Fehler bei {video_id}: {e}")
            continue
    
    return videos


def import_youtube_playlist_simple(playlist_obj):
    """
    Importiert von JEDER YouTube URL
    """
    from .models import Video, PlaylistItem
    
    url = playlist_obj.youtube_playlist_url
    if not url:
        return False, "Keine URL vorhanden", 0
    
    print(f"\n{'='*60}")
    print(f"IMPORT START: {url}")
    print(f"{'='*60}\n")
    
    # Universal Import
    videos_data = import_from_any_youtube_url(url)
    
    if not videos_data:
        return False, "Keine Videos gefunden. Ist die URL korrekt und die Seite erreichbar?", 0
    
    print(f"\n✅ {len(videos_data)} Videos gefunden")
    
    imported_count = 0
    errors = []
    
    for idx, video_data in enumerate(videos_data):
        try:
            # Video erstellen oder aktualisieren
            video, created = Video.objects.get_or_create(
                source_url=video_data['url'],
                defaults={
                    'title': video_data['title'][:250],
                    'thumbnail': video_data['thumbnail'],
                    'source_type': 'youtube',
                    'is_active': True,
                }
            )
            
            if not created:
                video.title = video_data['title'][:250]
                video.thumbnail = video_data['thumbnail']
                video.save()
            
            # Zur Playlist hinzufügen
            PlaylistItem.objects.get_or_create(
                playlist=playlist_obj,
                video=video,
                defaults={'order': idx}
            )
            
            imported_count += 1
            print(f"  ✓ {video_data['title'][:60]}")
            
        except Exception as e:
            error_msg = f"Video {video_data.get('video_id', '?')}: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ {error_msg}")
            continue
    
    # Zeitstempel aktualisieren
    playlist_obj.last_import = timezone.now()
    playlist_obj.save()
    
    print(f"\n{'='*60}")
    print(f"IMPORT FERTIG: {imported_count} von {len(videos_data)} Videos importiert")
    print(f"{'='*60}\n")
    
    if imported_count > 0:
        return True, f"Import erfolgreich", imported_count
    else:
        error_msg = f"Kein Video importiert. Fehler: {'; '.join(errors[:3])}"
        return False, error_msg, 0


def get_youtube_thumbnail(video_id, quality='maxresdefault'):
    """Erstellt YouTube Thumbnail URL"""
    return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"


def get_youtube_embed_url(video_id):
    """Erstellt YouTube Embed URL"""
    return f"https://www.youtube.com/embed/{video_id}"
