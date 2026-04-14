#!/usr/bin/env python
"""
RSL TV - Setup Script für Serien-System
Führt die notwendigen Migrationen und Setup-Schritte aus
"""

import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rsl_tv.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.core.management import call_command
from django.db import connection

def main():
    print("=" * 80)
    print("RSL TV - Serien-System Setup")
    print("=" * 80)
    print()
    
    # 1. Migrations erstellen
    print("📝 Erstelle Migrationen...")
    try:
        call_command('makemigrations', 'tv', verbosity=2)
        print("✅ Migrationen erstellt\n")
    except Exception as e:
        print(f"⚠️  Warnung bei makemigrations: {e}\n")
    
    # 2. Migrations anwenden
    print("🔄 Wende Migrationen an...")
    try:
        call_command('migrate', verbosity=2)
        print("✅ Migrationen angewendet\n")
    except Exception as e:
        print(f"❌ Fehler bei migrate: {e}\n")
        return False
    
    # 3. Prüfe ob Tabellen existieren
    print("🔍 Prüfe Datenbank-Tabellen...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name IN ('tv_series', 'tv_season', 'tv_episode')
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        if len(tables) == 3:
            print(f"✅ Alle Serien-Tabellen vorhanden: {', '.join(tables)}\n")
        else:
            print(f"⚠️  Nur {len(tables)} von 3 Tabellen gefunden: {', '.join(tables)}\n")
    
    # 4. Template Tags prüfen
    print("📂 Prüfe Template Tags...")
    templatetags_dir = os.path.join(os.path.dirname(__file__), 'tv', 'templatetags')
    if os.path.exists(os.path.join(templatetags_dir, 'tv_filters.py')):
        print("✅ Template Tags vorhanden\n")
    else:
        print("❌ Template Tags fehlen!\n")
    
    # 5. Statistiken anzeigen
    print("=" * 80)
    print("📊 Aktuelle Statistiken")
    print("=" * 80)
    
    from tv.models import Series, Season, Episode, Video, LiveStream, PlaylistItem
    
    stats = {
        'Serien': Series.objects.count(),
        'Staffeln': Season.objects.count(),
        'Episoden': Episode.objects.count(),
        'Videos': Video.objects.count(),
        'Live-Streams': LiveStream.objects.count(),
        'Playlists': PlaylistItem.objects.count(),
    }
    
    for name, count in stats.items():
        print(f"  {name}: {count}")
    
    print()
    print("=" * 80)
    print("✅ Setup abgeschlossen!")
    print("=" * 80)
    print()
    print("🚀 Nächste Schritte:")
    print("   1. Server starten: python manage.py runserver")
    print("   2. Admin öffnen: http://127.0.0.1:8000/admin/")
    print("   3. Serien hinzufügen unter 'TV' → 'Serien'")
    print("   4. Serien ansehen: http://127.0.0.1:8000/serien/")
    print()
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
