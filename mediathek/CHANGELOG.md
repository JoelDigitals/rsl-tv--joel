# RSL Mediathek - Änderungsübersicht

## 📦 Was ist neu?

Diese Version enthält umfassende Verbesserungen der Admin-Oberfläche und neue Funktionen für die Mediathek-Verwaltung.

---

## ✨ Hauptfunktionen

### 1. ⏰ Verfallsdatum-System
**Neu in Models:**
- `Video.available_until` - Videos automatisch nach Datum ausblenden
- `Series.available_until` - Ganze Serien zeitlich begrenzen
- `LiveStream.scheduled_end` - Geplantes Ende für Streams
- `LiveStream.available_until` - Aufzeichnungen zeitlich begrenzen

**Methoden hinzugefügt:**
- `Video.is_available()` - Prüft ob Video noch verfügbar
- `Series.is_available()` - Prüft ob Serie noch verfügbar

### 2. 🎬 YouTube Playlist Import
**Neu in Models:**
- `Playlist.youtube_playlist_url` - URL zur YouTube-Playlist
- `Playlist.last_import` - Zeitstempel des letzten Imports
- `Playlist.auto_import` - Automatisches Aktualisieren aktivieren

**Neue Datei:** `youtube_import.py`
- Hilfsfunktionen für YouTube-Integration
- Playlist-ID Extraktion
- Video-ID Extraktion
- API-Integration vorbereitet (API-Key erforderlich)

### 3. 🎨 Verbesserter Admin

**Alle Admin-Klassen überarbeitet mit:**
- 📋 Ausführliche Docstrings (Erklärung was der Bereich macht)
- 🎯 Fieldsets mit Beschreibungen
- 🏷️ Farbcodierte Status-Badges
- 📊 Verbesserte Listen-Ansichten
- ⚡ Custom Actions (z.B. YouTube Import)

**Status-Badges:**
- ✅ Grün = Aktiv/Verfügbar
- 🔴 Rot = Live/Kritisch
- ⏰ Gelb = Abgelaufen/Warnung
- ⚫ Grau = Inaktiv/Offline

---

## 📝 Geänderte Dateien

### `models.py`
```python
# Neue Felder hinzugefügt (keine Änderung an bestehenden Feldern):
- Video.available_until (DateTimeField, null=True)
- Series.available_until (DateTimeField, null=True)
- LiveStream.scheduled_end (DateTimeField, null=True)
- LiveStream.available_until (DateTimeField, null=True)
- Playlist.youtube_playlist_url (URLField)
- Playlist.last_import (DateTimeField, null=True)
- Playlist.auto_import (BooleanField, default=False)

# Neue Methoden:
- Video.is_available()
- Series.is_available()
```

### `admin.py` (komplett neu)
```python
# Alle Admin-Klassen überarbeitet:

@admin.register(Category)
class CategoryAdmin:
    + Docstring mit Erklärung
    + Fieldsets mit Beschreibungen
    + video_count() Display-Methode

@admin.register(Video)
class VideoAdmin:
    + Ausführliche Beschreibungen
    + availability_status() mit farbigen Badges
    + Gruppierte Fieldsets

@admin.register(Series)
class SeriesAdmin:
    + SeasonInline mit episode_count
    + availability_status()
    + season_count()

@admin.register(LiveStream)
class LiveStreamAdmin:
    + status_display() (LIVE/Geplant/Offline)
    + scheduled_times() Formatierung
    + availability_status()

@admin.register(Playlist)
class PlaylistAdmin:
    + youtube_status() Badge
    + import_youtube_playlist() Action
    + last_import_display()

@admin.register(Advertisement)
class AdvertisementAdmin:
    + Farbcodierte position_badge()
    + CTR mit Icons und Farben
    + Übersichtliche Feldgruppierung

# Admin Site Anpassung:
- site_header = "RSL Mediathek Administration"
- site_title = "RSL Admin"
- index_title = "Willkommen im RSL Mediathek Admin-Bereich"
```

### `youtube_import.py` (neu)
```python
# Hilfsfunktionen:
- extract_playlist_id(url)
- extract_video_id(url)
- get_video_info_from_id(video_id)
- import_youtube_playlist(playlist_obj, api_key)
- parse_iso8601_duration(duration_str)
- get_youtube_thumbnail(video_id, quality)
- get_youtube_embed_url(video_id)
- validate_youtube_url(url)
```

### `ADMIN_README.md` (neu)
Umfassende Dokumentation für Admins:
- Übersicht aller Admin-Bereiche
- Schritt-für-Schritt Anleitungen
- YouTube API Setup
- Tipps & Tricks
- Checklisten

---

## 🚀 Installation & Migration

### Schritt 1: Dateien ersetzen
```bash
# Alte Dateien sichern (optional)
cp models.py models.py.backup
cp admin.py admin.py.backup

# Neue Dateien aus mediathek_updated.zip extrahieren
unzip mediathek_updated.zip
cp mediathek_updated/* dein_projekt/deine_app/
```

### Schritt 2: Migrationen erstellen
```bash
python manage.py makemigrations
python manage.py migrate
```

**Erwartete Migrationen:**
- Video: available_until hinzufügen
- Series: available_until hinzufügen
- LiveStream: scheduled_end, available_until hinzufügen
- Playlist: youtube_playlist_url, last_import, auto_import hinzufügen

### Schritt 3: YouTube API (Optional)
Für YouTube-Import-Funktion:

1. Google Cloud Console: https://console.cloud.google.com/
2. Neues Projekt erstellen
3. YouTube Data API v3 aktivieren
4. API-Schlüssel erstellen
5. In `settings.py` eintragen:
```python
YOUTUBE_API_KEY = 'dein-api-key-hier'
```

---

## 🎯 Neue Admin-Features im Detail

### Kategorie-Verwaltung
- **Video-Zähler**: Zeigt Anzahl aktiver Videos pro Kategorie
- **Klare Beschreibungen**: Was sind Kategorien und wofür?

### Video-Verwaltung
- **Verfügbarkeits-Status**: Farbcodiert mit Tagen bis Ablauf
- **Automatische Thumbnails**: YouTube-Thumbnails werden automatisch geholt
- **Feldgruppen**: Übersichtliche Organisation in Sections

### Serien-Verwaltung
- **Inline Staffeln**: Staffeln direkt in der Serie bearbeiten
- **Episode-Zähler**: Pro Staffel Anzahl der Episoden
- **Verfügbarkeits-Management**: Ganze Serie auf einmal zeitlich begrenzen

### Livestream-Verwaltung
- **Live-Status-Badge**: 🔴 LIVE / 📅 Geplant / ⚫ Offline
- **Zuschauerzähler**: Aktuelle Viewer-Anzahl in Echtzeit
- **Zeitplanung**: Start- und Endzeit für geplante Events
- **Aufzeichnungs-Verfügbarkeit**: Wie lange bleibt Recording online?

### Playlist mit YouTube-Import
- **Import-Status-Badge**: ✅ Auto-Import / 📋 Manuell / ➕ Manuelle Playlist
- **Bulk-Action**: Mehrere Playlists auf einmal importieren
- **Letzter Import**: Zeitstempel wann zuletzt importiert
- **Auto-Update**: Aktivieren für regelmäßige Synchronisation

### Werbung-Verwaltung
- **Position-Badges**: Farbcodiert nach Placement (Pre-Roll, Banner, etc.)
- **Status-Badges**: Mit Icons (⏳ Pending, ✅ Active, ⏸️ Paused, ❌ Expired)
- **CTR-Anzeige**: Mit Icons je nach Performance (🔥 >2%, ⚠️ 0.5-1%, 📉 <0.5%)
- **Datum-Bereich**: Start- und Enddatum übersichtlich

---

## 📱 Mobile-Optimierung

Das Design bleibt **vollständig erhalten**:
- ✅ RSL-Farbschema unverändert
- ✅ Navigation responsive
- ✅ Touch-optimierte Buttons
- ✅ Mobile-freundliche Formulare

**Farben beibehalten:**
```css
--rsl-blue:       #0a6eb4
--rsl-blue-dark:  #073e6e
--rsl-dark:       #070d14
--rsl-accent:     #00c4ff
--rsl-live:       #e63946
```

---

## ⚠️ Wichtige Hinweise

### Migrations-Dateien
**Wie gewünscht:** Keine Änderungen an bestehenden Migration-Dateien in `migrations/` Ordner.

Neue Migrationen musst du selbst erstellen:
```bash
python manage.py makemigrations
```

### Rückwärts-Kompatibilität
Alle neuen Felder sind **optional** (`null=True, blank=True`):
- Bestehende Daten bleiben unverändert
- Keine Datenverluste
- Neue Features optional nutzbar

### API-Key für YouTube
Ohne API-Key funktioniert:
- ✅ Alles andere normal
- ✅ Manuelle Video-Eingabe
- ✅ Manuelle Playlists
- ❌ Automatischer YouTube-Import

Mit API-Key:
- ✅ Automatischer Playlist-Import
- ✅ Metadaten automatisch holen
- ✅ Regelmäßige Updates

---

## 📊 Übersicht: Was wurde NICHT verändert

✅ Bestehende Model-Felder unverändert
✅ Migrations-Dateien unverändert
✅ Views unverändert
✅ URLs unverändert
✅ Templates unverändert (außer Logo-Text falls gewünscht)
✅ Grundlegendes Design & Farben unverändert
✅ Datenbank-Schema kompatibel

---

## 🎉 Zusammenfassung

### Hinzugefügt:
- ✅ Verfallsdatum-System für alle Inhalte
- ✅ YouTube Playlist Import mit Auto-Update
- ✅ Komplett überarbeitete Admin-Oberfläche
- ✅ Farbcodierte Status-Badges
- ✅ Ausführliche Dokumentation
- ✅ Hilfe-Texte in jedem Admin-Bereich

### Verbessert:
- ✅ Admin-Übersichtlichkeit durch Fieldsets
- ✅ Status-Anzeigen mit Icons und Farben
- ✅ Inline-Editing für Staffeln und Episoden
- ✅ Custom Actions (YouTube Import)
- ✅ Statistik-Anzeigen (CTR, Viewer, etc.)

### Beibehalten:
- ✅ Alle bestehenden Funktionen
- ✅ RSL-Design und Farben
- ✅ Mobile-Optimierung
- ✅ Datenbank-Struktur

---

## 📞 Support & Hilfe

**Im Admin:** Jeder Bereich hat jetzt ausführliche Beschreibungen
**Dokumentation:** Siehe `ADMIN_README.md`
**Inline-Hilfe:** Hover über Feld-Labels für Tooltips

---

**Version:** 2.0 - RSL Mediathek Extended
**Datum:** April 2026
**Kompatibel mit:** Django 3.2+

Viel Erfolg! 🚀
