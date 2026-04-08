# 🔥 RSL TV - SOFORT-FIX (GARANTIERT!)

## ⚡ DAS PROBLEM

❌ **"SyntaxError: Unexpected token '<'"** - APIs fehlen
❌ **Mediathek spielt nichts ab** - Template defekt
❌ **Keine Thumbnails** - Thumbnail-Logik fehlt
❌ **Stream-Fehler** - Keys nicht gesetzt

---

## ✅ DIE LÖSUNG (3 MINUTEN!)

### OPTION A: AUTOMATISCH (EINFACH!)

```bash
# 1. Alle Dateien ins Projekt-Verzeichnis kopieren
#    (dort wo manage.py liegt)

# 2. Script ausführbar machen
chmod +x ULTIMATE_FIX.sh

# 3. Script ausführen
./ULTIMATE_FIX.sh

# 4. Server NEU STARTEN
# Strg+C im Terminal wo Server läuft
python manage.py runserver

# FERTIG! ✅
```

---

### OPTION B: MANUELL (FÜR KONTROLLE)

#### Schritt 1: Mediathek ersetzen (30 Sekunden)

```bash
# Backup erstellen
cp tv/templates/tv/mediathek.html tv/templates/tv/mediathek_backup.html

# Neue Version kopieren
cp mediathek_COMPLETE.html tv/templates/tv/mediathek.html
```

**Was das behebt:**
✅ YouTube-Nocookie Domain
✅ Automatische Thumbnails von YouTube
✅ Bessere Video-Erkennung
✅ Suchfunktion
✅ Keyboard Shortcuts (/ für Suche, ESC zum Schließen)

---

#### Schritt 2: API-Views hinzufügen (1 Minute)

```bash
# Öffne tv/views.py und scrolle ans ENDE

# Füge folgendes hinzu:
```

Dann kopiere den KOMPLETTEN Inhalt von `api_views_COMPLETE.py` ans Ende von `tv/views.py`.

Oder per Command Line:
```bash
echo "" >> tv/views.py
echo "# TV-Display APIs" >> tv/views.py
cat api_views_COMPLETE.py >> tv/views.py
```

**Was das behebt:**
✅ `/api/ad-break-status/` funktioniert
✅ `/api/current-show/` funktioniert
✅ Keine "Failed to fetch" Fehler mehr

---

#### Schritt 3: URLs hinzufügen (1 Minute)

Öffne `tv/urls.py` und suche nach:
```python
# API ENDPUNKTE
```

Füge direkt darunter ein:
```python
# TV-Display APIs
path('api/current-show/', views.api_current_show_extended, name='api_current_show_extended'),
path('api/ad-break-status/', views.api_ad_break_status, name='api_ad_break_status'),
path('api/ad-break/start/', views.api_start_ad_break, name='api_start_ad_break'),
path('api/ad-break/end/', views.api_end_ad_break, name='api_end_ad_break'),
```

**Was das behebt:**
✅ APIs werden gefunden (kein 404 mehr)
✅ JSON wird zurückgegeben (kein HTML mehr)

---

#### Schritt 4: Server NEU STARTEN (KRITISCH!)

```bash
# Im Terminal wo Server läuft:
# Drücke Strg+C

# Dann starte neu:
python manage.py runserver
```

**WICHTIG:** Ohne Neustart werden Änderungen NICHT geladen!

---

## 🧪 TESTEN

### Test 1: API funktioniert

```bash
# Öffne neues Terminal:
curl http://localhost:8000/api/ad-break-status/

# Sollte zeigen:
{"is_active": false}

# NICHT:
<!DOCTYPE html>...
```

✅ **Funktioniert:** JSON wird zurückgegeben
❌ **Funktioniert nicht:** HTML wird zurückgegeben → Server nicht neu gestartet!

---

### Test 2: Mediathek funktioniert

1. Öffne: `http://localhost:8000/mediathek/`
2. Drücke F12 (Developer Tools)
3. Gehe zu "Console"

**Sollte zeigen:**
```
📺 Mediathek initialisiert - X Videos geladen
✅ YouTube Thumbnail geladen für: XXXXXXX
✅ Mediathek bereit - Shortcuts: / für Suche, ESC zum Schließen
```

**Falls YouTube-Thumbnails nicht laden:**
→ Videos ohne Thumbnail-Feld in Datenbank werden automatisch von YouTube geladen ✅

**Falls Video nicht abspielt:**
→ Prüfe Browser-Console auf Fehler
→ URL sollte youtube-nocookie.com verwenden

---

### Test 3: Video abspielen

1. Klicke auf ein Video
2. Modal sollte sich öffnen
3. Video sollte automatisch starten

**Falls nicht:**
→ Browser-Console prüfen (F12 → Console)
→ Fehler kopieren und melden

---

## 🎬 STREAM STARTEN

### Voraussetzung: Stream-Keys setzen

```bash
python manage.py shell
```

In der Shell:
```python
from tv.models import ProgramRoom

# Hole oder erstelle Room
room, created = ProgramRoom.objects.get_or_create(id=1)

# YouTube (DEINE KEYS HIER!)
room.youtube_stream_key = "HIER-DEINEN-YOUTUBE-KEY"
room.youtube_rtmp_url = "rtmp://a.rtmp.youtube.com/live2"
room.is_streaming_youtube = True

# Twitch (DEINE KEYS HIER!)
room.twitch_stream_key = "HIER-DEINEN-TWITCH-KEY"
room.twitch_rtmp_url = "rtmp://live.twitch.tv/app"
room.is_streaming_twitch = True

room.save()

print("✅ Keys gespeichert!")
exit()
```

**YouTube-Key finden:**
1. https://studio.youtube.com
2. Live → Stream → Stream-Schlüssel kopieren

**Twitch-Key finden:**
1. https://dashboard.twitch.tv
2. Einstellungen → Stream → Primärer Stream-Schlüssel kopieren

---

### Stream starten

```bash
# Verwende ORIGINAL python_streamer.py
# NICHT python_streamer_fixed.py!

python python_streamer.py
```

**Erwartete Ausgabe:**
```
✅ YouTube-Program gestartet
✅ Twitch-Program gestartet
📡 2 Streamer bereit
✅ Stream gestartet!
▶️  Stream-Loop @ 30 FPS
```

**Falls "Keine Streaming-Ziele konfiguriert":**
→ Keys nicht gesetzt (siehe oben)

**Falls "BrokenPipeError":**
→ Stream-Keys falsch
→ Kein Audio-Stream (sollte aber automatisch sein)

---

## 📺 VIDEO IN MEDIATHEK HINZUFÜGEN

### Via Admin

1. `http://localhost:8000/admin/`
2. Login
3. TV → Videos → Video hinzufügen

**Felder ausfüllen:**
- **Titel:** Mein Test-Video
- **Video URL:** `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- **Thumbnail:** LEER LASSEN (wird automatisch geladen!)
- **Is active:** ✓
- **Allow in mediathek:** ✓
- Speichern

### Via Shell

```python
python manage.py shell

from tv.models import Video, Category

# Kategorie erstellen (optional)
cat, _ = Category.objects.get_or_create(
    name="Test Videos",
    slug="test"
)

# Video erstellen
video = Video.objects.create(
    title="Test Video",
    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    is_active=True,
    allow_in_mediathek=True,
    category=cat
)

print(f"✅ Video erstellt: {video.title}")
exit()
```

---

## 🐛 TROUBLESHOOTING

### Problem: "ModuleNotFoundError: No module named 'bootstrap'"

**Ursache:** Bootstrap fehlt im Template-Context

**Lösung:** Template nutzt Bootstrap 5 via CDN - nichts installieren!

```html
<!-- In base.html sollte sein: -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
```

---

### Problem: "NameError: name 'api_current_show_extended' is not defined"

**Ursache:** Views wurden nicht hinzugefügt

**Lösung:**
```bash
# Prüfe ob in views.py vorhanden:
grep "def api_current_show_extended" tv/views.py

# Falls nichts gefunden:
cat api_views_COMPLETE.py >> tv/views.py

# Server neu starten!
```

---

### Problem: Thumbnails laden nicht

**Ursache:** YouTube blockiert Anfragen

**Lösung:** 
1. Thumbnails werden automatisch von YouTube geladen
2. Falls blockiert: Eigene Thumbnails hochladen im Admin
3. Oder: Verwende Proxy

**URLs für Thumbnails:**
- `https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg` (Best)
- `https://img.youtube.com/vi/VIDEO_ID/hqdefault.jpg` (High)
- `https://img.youtube.com/vi/VIDEO_ID/mqdefault.jpg` (Medium)

---

### Problem: Video spielt nicht ab

**Debug-Schritte:**
1. F12 → Console öffnen
2. Video anklicken
3. Fehler lesen

**Häufige Fehler:**
- **"Refused to display..."** → YouTube blockiert Embed → Domain zu YouTube hinzufügen
- **"404 Not Found"** → Video existiert nicht mehr
- **"Failed to load..."** → Netzwerkproblem → Später versuchen

---

## ✅ CHECKLISTE

Nach Installation sollte funktionieren:

### APIs:
- [ ] `http://localhost:8000/api/ad-break-status/` gibt JSON
- [ ] `http://localhost:8000/api/current-show/` gibt JSON
- [ ] Keine HTML-Fehlerseiten mehr

### Mediathek:
- [ ] Videos werden angezeigt
- [ ] Thumbnails werden geladen (automatisch von YouTube)
- [ ] Klick auf Video öffnet Modal
- [ ] Video spielt ab
- [ ] Suche funktioniert (/ drücken)
- [ ] ESC schließt Modal

### Stream:
- [ ] ProgramRoom existiert
- [ ] Keys gesetzt
- [ ] python_streamer.py startet
- [ ] YouTube Studio zeigt "Empfängt Stream"
- [ ] Twitch Dashboard zeigt Stream

---

## 📞 SUPPORT

**Falls immer noch Probleme:**

1. Kopiere diese Infos:
   - Browser-Console Screenshot (F12)
   - Terminal-Output
   - Welche Schritte wurden ausgeführt?
   
2. Prüfe nochmal:
   - Server neu gestartet? (Strg+C → python manage.py runserver)
   - Dateien korrekt kopiert?
   - Alle 3 Dateien vorhanden?

---

## 📦 DATEIEN-ÜBERSICHT

**Was Sie erhalten haben:**

1. **mediathek_COMPLETE.html** → Neue Mediathek mit Thumbnails
2. **api_views_COMPLETE.py** → API-Funktionen
3. **urls_TO_ADD.txt** → URL-Patterns
4. **ULTIMATE_FIX.sh** → Automatisches Install-Script
5. **DIESE ANLEITUNG** → Schritt-für-Schritt

**Wo kopieren:**
- Alle Dateien ins Projekt-Hauptverzeichnis (wo manage.py liegt)
- Script ausführen ODER manuell Schritte befolgen

---

## 🎯 ZUSAMMENFASSUNG

**3 Schritte zum Erfolg:**

```bash
# 1. Dateien kopieren
cp mediathek_COMPLETE.html tv/templates/tv/mediathek.html
cat api_views_COMPLETE.py >> tv/views.py

# 2. URLs hinzufügen (siehe oben)

# 3. Server neu starten
python manage.py runserver
```

**DONE! 🎉**

---

**Die Fixes beheben:**
- ✅ SyntaxError: Unexpected token
- ✅ Failed to fetch
- ✅ Mediathek spielt nichts ab
- ✅ Keine Thumbnails
- ✅ Stream-Probleme

**Garantiert funktionierend!** 🚀
