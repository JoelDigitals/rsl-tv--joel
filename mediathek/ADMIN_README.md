# RSL Mediathek - Admin Dokumentation

## 🎯 Übersicht

Die RSL Mediathek ist eine umfassende Video- und Streaming-Plattform mit erweiterten Admin-Funktionen.

### Neue Features in dieser Version:

✅ **Verfallsdatum für Inhalte** - Videos, Serien und Streams können zeitlich begrenzt werden
✅ **YouTube Playlist Import** - Automatischer Import ganzer YouTube-Playlists
✅ **Verbesserte Admin-Oberfläche** - Klare Beschreibungen und bessere Organisation
✅ **Mobile-optimiert** - Responsive Design mit RSL-Farben

---

## 📋 Admin-Bereiche

### 1. Kategorien
**Was**: Organisationskategorien für Videos und Streams
**Verwendung**: Erstelle Kategorien wie "Sport", "News", "Entertainment"
- `name`: Name der Kategorie
- `slug`: URL-freundlicher Name (automatisch generiert)
- `is_active`: Kategorie aktivieren/deaktivieren

### 2. Videos
**Was**: Einzelne Videos von YouTube, Vimeo oder anderen Quellen
**Neue Felder**:
- `available_until`: Optional - Nach diesem Datum wird das Video automatisch ausgeblendet
- `published_at`: Veröffentlichungsdatum
- `views`: Automatisch gezählt

**Tipps**:
- YouTube-URL einfach in `source_url` einfügen
- Thumbnail wird automatisch geholt, kann aber überschrieben werden
- Dauer in Sekunden angeben (z.B. 3600 = 1 Stunde)

### 3. Serien
**Was**: Mehrteilige Inhalte mit Staffeln und Episoden
**Neue Felder**:
- `available_until`: Gesamte Serie zeitlich begrenzen
- Staffeln direkt in der Serie bearbeiten (Inline)

**Workflow**:
1. Serie erstellen
2. Staffeln hinzufügen (direkt in der Serie)
3. In jeder Staffel Episoden hinzufügen
4. Episoden mit YouTube-URLs verknüpfen

### 4. Livestreams
**Was**: Live-Übertragungen mit Zuschauerzählung und Chat
**Neue Felder**:
- `scheduled_start`: Wann beginnt der Stream?
- `scheduled_end`: Wann endet der Stream?
- `available_until`: Aufzeichnung verfügbar bis...
- `is_live`: ✅ = Stream läuft JETZT

**Live-Status**:
- 🔴 LIVE = Stream läuft gerade
- 📅 Geplant = Zukünftiger Stream
- ⚫ Offline = Nicht aktiv

### 5. Playlists mit YouTube Import 🎬
**Was**: Sammlungen von Videos ODER YouTube-Playlist-Import
**Neue Funktionalität**:

#### Manuelle Playlist:
1. Playlist erstellen
2. Videos über "Playlist Items" manuell hinzufügen

#### YouTube Import:
1. Playlist erstellen
2. `youtube_playlist_url` ausfüllen (z.B. `https://www.youtube.com/playlist?list=PLxxxxx`)
3. `auto_import` aktivieren für regelmäßige Updates
4. Aktion "🎬 YouTube Playlist importieren" ausführen

**YouTube API Setup** (für Produktiv-Betrieb):
```python
# In settings.py hinzufügen:
YOUTUBE_API_KEY = 'dein-api-key-hier'
```

API-Key erstellen:
1. https://console.cloud.google.com/
2. Projekt erstellen
3. YouTube Data API v3 aktivieren
4. API-Key erstellen
5. In settings.py eintragen

### 6. Werbung & Sponsoring 💰
**Advertisement**: Einzelne Werbeanzeigen
- Video-Ads (Pre-Roll, Mid-Roll, Post-Roll)
- Banner-Ads (Top, Side, Overlay)
- Targeting nach Kategorien
- Statistiken: Impressions, Clicks, CTR

**AdBreak**: Werbeunterbrechungen in Videos
- Zeitpunkt festlegen (z.B. nach 300 Sekunden)
- Mehrere Ads pro Break
- Überspringbar ja/nein

### 7. Live-Features
**ViewerSession**: Automatisch - Zeigt aktive Zuschauer
**ChatMessage**: Chat-Nachrichten aus Livestreams (Moderation)

---

## ⚙️ Wichtige Einstellungen

### Verfallsdatum-System

Alle Inhalte (Videos, Serien, Streams) können jetzt mit `available_until` zeitlich begrenzt werden:

```python
# Beispiel: Video nur 30 Tage verfügbar
from datetime import timedelta
from django.utils import timezone

video.available_until = timezone.now() + timedelta(days=30)
video.save()
```

**Frontend-Integration**:
Die Views sollten `is_available()` verwenden:
```python
# In views.py
available_videos = Video.objects.filter(
    is_active=True
).exclude(
    available_until__lt=timezone.now()
)
```

### Status-Badges

Admin zeigt farbcodierte Status:
- 🔴 **LIVE** (rot) - Stream läuft
- ✅ **Aktiv** (grün) - Verfügbar
- ⏰ **Abgelaufen** (gelb) - Verfallsdatum überschritten
- ❌ **Inaktiv** (grau) - Deaktiviert

---

## 🎨 Design & Farben

Die Plattform verwendet das RSL-Farbschema:

```css
--rsl-blue:       #0a6eb4  /* Hauptfarbe */
--rsl-blue-dark:  #073e6e  /* Dunkles Blau */
--rsl-blue-light: #1a8fd1  /* Helles Blau */
--rsl-dark:       #070d14  /* Hintergrund */
--rsl-accent:     #00c4ff  /* Akzent */
--rsl-live:       #e63946  /* Live-Rot */
```

Mobile-optimiert mit:
- Responsive Navigation
- Touch-freundliche Buttons
- Optimierte Formulare
- Swipe-Gesten (geplant)

---

## 🔧 Migration

**WICHTIG**: Migrations-Dateien werden NICHT angepasst wie gewünscht.

Nach dem Update Migrationen erstellen:
```bash
python manage.py makemigrations
python manage.py migrate
```

Neue Felder:
- `Video.available_until`
- `Series.available_until`
- `LiveStream.scheduled_end`
- `LiveStream.available_until`
- `Playlist.youtube_playlist_url`
- `Playlist.last_import`
- `Playlist.auto_import`

---

## 📝 Checkliste für den Betrieb

### Basis-Setup:
- [ ] Kategorien anlegen
- [ ] Erste Videos hinzufügen
- [ ] Navigation testen

### Erweitert:
- [ ] Serien mit Staffeln einrichten
- [ ] YouTube Playlist importieren
- [ ] Livestreams planen
- [ ] Werbung konfigurieren

### YouTube Integration:
- [ ] YouTube API Key erstellen
- [ ] In settings.py eintragen
- [ ] Playlist-Import testen
- [ ] Auto-Import für Updates aktivieren

### Wartung:
- [ ] Regelmäßig abgelaufene Inhalte prüfen
- [ ] Werbestatistiken analysieren
- [ ] Chat moderieren
- [ ] Zuschauerzahlen überwachen

---

## 🚀 Tipps & Tricks

### YouTube Videos schnell hinzufügen:
1. YouTube URL kopieren
2. Admin → Videos → "Video hinzufügen"
3. Nur `title` und `source_url` ausfüllen
4. Rest wird automatisch geholt

### Serien-Staffeln organisieren:
- Nutze klare Namenskonventionen
- Staffel-Titel optional für bessere Übersicht
- Episode-Nummern durchlaufend

### Werbung optimieren:
- CTR über 2% = 🔥 Sehr gut
- CTR unter 0.5% = 📉 Optimieren
- Pre-Roll für maximale Reichweite
- Mid-Roll nur bei langen Videos (>10 Min)

### Livestream-Planung:
1. Event mit `scheduled_start` anlegen
2. Status: 📅 Geplant
3. Vor Start: `is_live` auf True
4. Stream-URL eintragen
5. Nach Ende: `is_live` auf False

---

## 📞 Support

Bei Fragen oder Problemen:
- Admin-Bereich: Beschreibungen in jedem Abschnitt
- Inline-Hilfe: Hover über Feld-Labels
- Dokumentation: Diese Datei

---

## 🎉 Neue Admin-Features

✨ **Farbcodierte Status-Badges**
✨ **Inline-Editing** für Staffeln und Episoden
✨ **Bulk-Actions** für YouTube-Import
✨ **Statistik-Dashboards** für Werbung
✨ **Live-Zuschauerzählung**
✨ **Chat-Moderation**
✨ **Verfallsdatum-Warnung**

---

Viel Erfolg mit der RSL Mediathek! 🚀
