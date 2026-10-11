# 🚀 Quick Start - RSL Mediathek Update

## ⚡ Schnellinstallation

### 1. Dateien extrahieren
```bash
unzip mediathek_updated.zip
cd mediathek_updated
```

### 2. In dein Projekt kopieren
```bash
# Ersetze 'deine_app' mit deinem App-Namen
cp -r * /pfad/zu/deinem/projekt/deine_app/
```

### 3. Migrationen erstellen
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Admin aufrufen
```
http://localhost:8000/admin/
```

**Fertig!** ✅

---

## 📦 Was ist drin?

### ✨ Neue Features
- **Verfallsdatum** für Videos, Serien & Streams
- **YouTube Playlist Import** (mit Auto-Update)
- **Verbesserter Admin** mit Beschreibungen & Badges
- **Status-Anzeigen** (Live, Verfügbarkeit, CTR, etc.)

### 📁 Dateien im Paket
```
mediathek_updated/
├── admin.py              ← Komplett neuer Admin
├── models.py             ← Erweiterte Models (+7 neue Felder)
├── youtube_import.py     ← Neu: YouTube Import Funktionen
├── ADMIN_README.md       ← Ausführliche Dokumentation
├── CHANGELOG.md          ← Alle Änderungen im Detail
├── views.py              ← Unverändert
├── urls.py               ← Unverändert
├── models_ads.py         ← Unverändert
├── apps.py               ← Unverändert
├── __init__.py           ← Unverändert
└── templates/            ← Unverändert
```

---

## 🎯 Wichtigste Änderungen

### Models erweitert (7 neue Felder):
```python
Video.available_until          # Verfallsdatum
Series.available_until         # Verfallsdatum
LiveStream.scheduled_end       # Geplantes Ende
LiveStream.available_until     # Aufzeichnung verfügbar bis
Playlist.youtube_playlist_url  # YouTube Playlist URL
Playlist.last_import           # Letzter Import
Playlist.auto_import           # Auto-Update aktivieren
```

### Admin komplett überarbeitet:
- ✅ Beschreibungen in jedem Bereich
- ✅ Farbcodierte Status-Badges
- ✅ YouTube Import-Action
- ✅ Inline-Editing (Staffeln, Episoden)
- ✅ Statistik-Anzeigen (CTR, Viewer, etc.)

---

## 🎬 YouTube Import nutzen

### Ohne API-Key (Demo):
1. Admin → Playlists → Playlist hinzufügen
2. `youtube_playlist_url` einfügen
3. Action: "🎬 YouTube Playlist importieren"
4. → Zeigt erkannte Playlist-ID

### Mit API-Key (Produktiv):
1. Google Cloud Console → YouTube Data API v3 aktivieren
2. API-Key erstellen
3. In `settings.py`:
   ```python
   YOUTUBE_API_KEY = 'dein-api-key'
   ```
4. Import läuft automatisch mit allen Metadaten

---

## 📊 Neue Admin-Features

### Kategorien
- Zeigt Anzahl Videos pro Kategorie

### Videos
- Status: ✅ Aktiv / ⏰ Abgelaufen / ❌ Inaktiv
- Tage bis Ablauf anzeigen

### Serien
- Inline Staffel-Bearbeitung
- Episode-Zähler pro Staffel

### Livestreams
- Status: 🔴 LIVE / 📅 Geplant / ⚫ Offline
- Aktuelle Zuschauerzahl
- Zeitplanung (Start/Ende)

### Playlists
- Import-Status: ✅ Auto / 📋 Manuell / ➕ Neu
- YouTube Import per Button
- Letzter Import-Zeitstempel

### Werbung
- Position-Badges (farbcodiert)
- CTR mit Icons: 🔥 >2% / ⚠️ 0.5-1% / 📉 <0.5%
- Status: ⏳ ✅ ⏸️ ❌

---

## ⚙️ Wichtige Hinweise

### ✅ Kompatibilität
- Alle neuen Felder sind **optional**
- Bestehende Daten bleiben **unverändert**
- Migrations-Dateien **nicht geändert** (wie gewünscht)
- **Rückwärts-kompatibel**

### 🎨 Design
- RSL-Farben **beibehalten**
- Mobile-optimiert **beibehalten**
- Navigation **unverändert**

### 📱 Was funktioniert ohne Änderung?
- ✅ Alle Views
- ✅ Alle Templates
- ✅ Alle URLs
- ✅ Alle APIs
- ✅ Frontend komplett

---

## 📖 Dokumentation

### Für Admins:
📄 **ADMIN_README.md** - Ausführliche Anleitung für jeden Admin-Bereich

### Für Entwickler:
📄 **CHANGELOG.md** - Technische Details aller Änderungen

### Quick-Hilfe:
- Jeder Admin-Bereich hat Docstrings
- Fieldsets haben Beschreibungen
- Felder haben Hilfe-Texte

---

## 🆘 Probleme?

### Migration schlägt fehl?
```bash
# Alte Migrations zurücksetzen (optional)
python manage.py migrate deine_app zero
# Neu erstellen
python manage.py makemigrations
python manage.py migrate
```

### Admin sieht komisch aus?
- Browser-Cache leeren (Ctrl+F5)
- Static Files sammeln: `python manage.py collectstatic`

### YouTube Import funktioniert nicht?
- **Ohne API-Key:** Nur Demo-Modus, keine echten Imports
- **Mit API-Key:** In `settings.py` überprüfen

---

## ✅ Checkliste nach Installation

- [ ] Migrationen erstellt und ausgeführt
- [ ] Admin aufgerufen und getestet
- [ ] Kategorie erstellt (Test)
- [ ] Video hinzugefügt (Test)
- [ ] Verfallsdatum getestet
- [ ] YouTube URL ausprobiert
- [ ] Playlist erstellt
- [ ] (Optional) YouTube API-Key eingetragen
- [ ] Dokumentation gelesen

---

## 🎉 Los geht's!

1. **Jetzt:** Migrationen ausführen
2. **Dann:** Admin öffnen und staunen
3. **Danach:** ADMIN_README.md lesen
4. **Optional:** YouTube API einrichten

**Viel Erfolg mit der RSL Mediathek!** 🚀

---

**Support:** Beschreibungen direkt im Admin
**Docs:** ADMIN_README.md & CHANGELOG.md im Paket
**Version:** 2.0 Extended
