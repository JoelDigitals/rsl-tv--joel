# 📺 RSL TV – Django Fernsehsender System
**von Joel Digitals**

Ein vollständiges Django-basiertes TV-Sender-System mit 24/7 Stream, Werbebuchung, Programmplanung und mehr.

---

## 🚀 Features

- **24/7 Live-TV** via YouTube & Twitch
- **Automatischer Sendeplan** mit Wiederholungen
- **Live-Schaltungen** aus aller Welt (YouTube Live, Twitch, OBS/RTMP)
- **Werbesystem** mit Online-Buchungsformular und Zeitslots
- **Werbepausen** – automatisch nach X Minuten
- **Wasserzeichen** (RSL) auf dem Stream
- **Mediathek** für verpasste Sendungen
- **IPTV-Playlist** (M3U) für Smart TV
- **Laufschrift-News**
- **Supabase** als Datenbank
- **Deployment auf Render.com** (kostenlos)
- **FFmpeg-Script** für den 24/7 Stream (separater Server)

---

## 📁 Projektstruktur

```
rsl_tv/
├── rsl_tv/              # Django Hauptprojekt
│   ├── settings.py      # Einstellungen
│   ├── urls.py          # URL-Routing
│   └── wsgi.py
├── tv/                  # Haupt-App
│   ├── models.py        # Datenbankmodelle
│   ├── views.py         # Views & API
│   ├── urls.py          # URLs
│   ├── admin.py         # Admin-Panel
│   ├── forms.py         # Formulare
│   ├── serializers.py   # REST API
│   ├── context_processors.py
│   └── templates/tv/    # HTML-Templates
├── templates/           # Basis-Templates
├── static/              # CSS, JS, Bilder
├── ffmpeg_streamer.py   # 24/7 Stream-Script
├── requirements.txt
├── render.yaml          # Render.com Config
├── Procfile
└── .env.example
```

---

## 🛠️ Installation (Lokal)

### 1. Voraussetzungen
- Python 3.10+
- FFmpeg installiert (`sudo apt install ffmpeg` / `brew install ffmpeg`)
- Supabase-Konto (kostenlos auf supabase.com)

### 2. Projekt einrichten
```bash
git clone <your-repo>
cd rsl_tv

# Virtuelle Umgebung
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Abhängigkeiten
pip install -r requirements.txt

# Umgebungsvariablen
cp .env.example .env
# → .env mit Ihren Daten ausfüllen!
```

### 3. Supabase einrichten
1. Gehen Sie auf [supabase.com](https://supabase.com) und erstellen Sie ein neues Projekt
2. Unter **Settings → Database** finden Sie die Verbindungsdaten
3. Tragen Sie diese in Ihre `.env` ein:
   ```
   DB_HOST=db.IHRE-ID.supabase.co
   DB_PASSWORD=IhrPasswort
   ```

### 4. Datenbank & Server starten
```bash
python manage.py migrate
python manage.py createsuperuser  # Admin-Benutzer anlegen
python manage.py collectstatic
python manage.py runserver
```

🌐 Öffnen Sie: http://localhost:8000  
🔧 Admin: http://localhost:8000/admin

---

## 🌐 Deployment auf Render.com (Kostenlos)

### 1. GitHub Repository
Laden Sie das Projekt auf GitHub hoch.

### 2. Render.com
1. Account auf [render.com](https://render.com) erstellen
2. **New Web Service** → Ihr GitHub-Repo auswählen
3. Einstellungen:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start Command**: `gunicorn rsl_tv.wsgi:application --bind 0.0.0.0:$PORT`
4. **Environment Variables** hinzufügen (aus `.env`)
5. **Deploy**!

### 3. Wichtig: Render Free Plan
- Die App "schläft" nach 15 Min Inaktivität → erste Anfrage dauert ~30s
- Für 24/7-Betrieb: Upgrade auf Paid Plan oder Uptime-Monitor nutzen

---

## 📡 FFmpeg 24/7 Stream einrichten

Der Django-Server auf Render steuert das Programm – der eigentliche Stream muss auf einem **separaten System** laufen (lokal, VPS, etc.), da Render keinen dauerhaften FFmpeg-Prozess unterstützt.

### Option A: Lokal streamen
```bash
# Zusätzliche Abhängigkeiten
pip install requests yt-dlp python-dotenv

# .env anpassen:
RSL_API_URL=https://rsl-tv.onrender.com
YOUTUBE_STREAM_KEY=IhrStreamKey

# Starten
python ffmpeg_streamer.py
```

### Option B: Günstiger VPS (empfohlen)
- [Hetzner](https://www.hetzner.com): ab ~4€/Monat (CX11)
- [DigitalOcean](https://digitalocean.com): ab 4$/Monat
- Dort FFmpeg + Python installieren, Script hochladen, mit `screen` oder `systemd` dauerhaft laufen lassen.

### Option C: GitHub Actions (Workaround)
Für einfache Setups kann ein GitHub Action den Stream starten – begrenzt auf 6h pro Run.

---

## 🎬 Inhalte hinzufügen (Admin-Panel)

### Videos
1. http://localhost:8000/admin/tv/video/add/
2. Titel, URL (YouTube/Drive/Dropbox), Dauer eintragen
3. **Wichtig**: URL muss öffentlich oder ungelistet sein

### Sendeplan
1. http://localhost:8000/admin/tv/schedule/add/
2. Sendung, Start- und Endzeit, Video oder Live-Stream zuweisen
3. Werbepausen (AdSlots) können direkt im Sendeplan angelegt werden

### Live-Stream einschalten
1. http://localhost:8000/admin/tv/livestream/
2. Stream-URL eintragen (YouTube Live, Twitch, etc.)
3. **is_live** auf ✅ setzen → FFmpeg-Script wechselt automatisch

### Werbung genehmigen
1. http://localhost:8000/admin/tv/advertisement/
2. Eingegangene Buchungen prüfen
3. Status auf "Aktiv" setzen + "Bezahlt" ✅

---

## 📺 YouTube Live-Stream einrichten

1. YouTube Studio → **Live-Stream**
2. Stream-Key kopieren → in `.env` als `YOUTUBE_STREAM_KEY`
3. Stream-URL für Einbettung: `https://www.youtube.com/embed/live_stream?channel=CHANNEL_ID`
4. In `.env` als `YOUTUBE_CHANNEL_URL` eintragen

---

## 📱 IPTV / Smart TV

Die M3U-Playlist ist verfügbar unter:
```
https://IhreDomain.com/iptv/rsl.m3u
```

In IPTV-Apps (z.B. TiviMate, VLC, Smart IPTV) eintragen und RSL direkt auf dem TV schauen.

---

## 💰 Werbebuchung

Kunden können unter `/werbung/` Pakete ansehen und unter `/werbung/buchen/` online buchen.

**Preise (anpassbar in `views.py`):**
| Paket | Preis | Einblendungen |
|-------|-------|---------------|
| Starter | 49€ | 50 |
| Basic | 99€ | 150 |
| Standard | 199€ | 400 |
| Premium | 399€ | 1000 |
| Exklusiv | Anfrage | Individuell |

---

## 🔧 API-Endpunkte

| Endpoint | Beschreibung |
|----------|-------------|
| `GET /api/playlist/` | Aktuelle Playlist für FFmpeg |
| `GET /api/current/` | Aktuelle Sendung (Live-Ticker) |
| `GET /api/news/` | Laufschrift-Nachrichten |
| `POST /api/ad-played/<id>/` | Werbeeinblendung melden |
| `GET /iptv/rsl.m3u` | IPTV M3U Playlist |

---

## 📞 Support

- **E-Mail**: rsl@joeldigitals.de
- **Joel Digitals** – Betreiber von RSL

---

*RSL TV – Dein Sender. Deine Welt. | © 2024 Joel Digitals*


---

## 🆕 Update-Changelog (v2)

### ✅ Neu in dieser Version

**Logo-Wasserzeichen:**
- Upload über Admin → "Sender-Logo"
- Position wählbar: oben links / oben rechts / unten links / rechts
- Deckkraft und Größe einstellbar
- FFmpeg liest das Logo automatisch aus der API

**Werbepausen (geplant + Live):**
- Werbepausen explizit im Sendeplan planen (Zeit-Offset in Sekunden)
- Video wird bei Werbepause PAUSIERT – danach Fortsetzung ab gleicher Stelle
- Werbeblöcke automatisch aus Trailer + Spots + Outro zusammengestellt

**Live-Werbepausen:**
- Direkter Button im Admin bei jeder Live-Sendung
- "Werbepause STARTEN" → Live pausiert, Block läuft
- "Werbepause BEENDEN" → zurück zum Live-Stream

**Trailer / Outro Werbung:**
- Werbevideos kategorisierbar: Trailer (Einleitung), Spot (Hauptwerbung), Outro (Abschluss)
- Automatische Zufallsauswahl aus dem Pool

**Mailjet E-Mail (kein Stripe):**
- Buchungsbestätigung automatisch nach Formularabsendung
- Rechnung per E-Mail (manuell oder per Admin-Aktion)
- Freischaltungs-E-Mail nach Zahlungseingang
- Admin-Benachrichtigung bei neuer Buchung

**Rechnung statt Checkout:**
- Kein direktes Bezahlsystem
- Buchung → Bestätigung → Rechnung per Mail → Zahlung per Überweisung → Freischaltung
- Freischalten im Admin: Buchung auswählen → "Als bezahlt markieren & Spot freischalten"

**DATABASE_URL Support:**
- Supabase DATABASE_URL direkt in .env eintragen
- Automatisches SSL

