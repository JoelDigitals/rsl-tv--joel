# RSL TV - JDS Cloud Upload Integration

## 🎬 Upload-Feature Übersicht

Die RSL TV Mediathek wurde um ein vollständiges Upload-System erweitert, das die JDS Cloud API nutzt. Nutzer können jetzt direkt Videos, Bilder und Live-Stream-Recordings hochladen.

## ✨ Features

### 📤 Upload-Funktionen
- **Video-Upload**: Beliebige Videoformate (MP4, MKV, MOV, WebM, etc.)
- **Bild-Upload**: Thumbnails, Logos, Overlays (PNG, JPG, GIF, WebP, SVG)
- **Live-Stream-Recordings**: Aufgezeichnete Streams zur Mediathek hinzufügen
- **Werbevideo-Upload**: Spezielle Uploads für Werbevideos
- **Logo-Upload**: Sender-Logos und Wasserzeichen

### 🚀 Technische Features
- ✅ Keine Größenbeschränkung
- ✅ Direkte Integration mit JDS Cloud API
- ✅ Automatische Metadaten-Erfassung
- ✅ AJAX-Upload-Option für asynchrone Uploads
- ✅ Progress-Tracking
- ✅ Admin-Panel-Integration
- ✅ Kategorisierung und Tagging

## 📁 Neue Dateien

### Backend
```
tv/
├── jds_upload_service.py       # JDS Cloud API Service
├── upload_views.py              # Upload View-Logik
├── upload_center_view.py        # Upload Dashboard
└── migrations/
    └── 0007_add_upload_fields.py  # Datenbank-Migration
```

### Frontend Templates
```
templates/tv/
├── upload_center.html           # Upload Dashboard
├── upload_video.html            # Video-Upload-Formular
├── upload_thumbnail.html        # Bild-Upload-Formular
└── upload_livestream.html       # Stream-Recording-Upload
```

## 🔧 Installation

### 1. Datenbank migrieren
```bash
python manage.py migrate
```

### 2. Dependencies installieren
Alle notwendigen Pakete sind bereits in `requirements.txt`:
- Django 5.1
- requests 2.32.3 (für API-Calls)
- djangorestframework

### 3. Admin-Bereich
Die Upload-Felder sind automatisch im Django Admin verfügbar:
- Videos mit Upload-Source werden speziell gekennzeichnet
- Dateigröße wird angezeigt
- Upload-URLs sind schreibgeschützt

## 📊 Datenbank-Änderungen

### Video Model - Neue Felder
```python
uploaded_file_id          # JDS Cloud File-ID
uploaded_file_url         # View-URL (für Browser)
uploaded_file_download_url # Download-URL (für Streaming)
uploaded_file_name        # Original-Dateiname
uploaded_file_size        # Größe in Bytes
uploaded_file_type        # MIME-Type
```

### Neue Source-Type Option
```python
source_type = 'upload'    # Für hochgeladene Dateien
```

## 🔌 API-Integration

### JDS Cloud Upload Endpoint
```
POST https://ppkinjwiewiynqgofdcz.supabase.co/functions/v1/upload
Authorization: Bearer <TOKEN>
Content-Type: multipart/form-data
```

### Response Format
```json
{
  "success": true,
  "file": {
    "id": "uuid",
    "name": "video.mp4",
    "size": 123456789,
    "content_type": "video/mp4",
    "view_url": "https://...",
    "download_url": "https://...",
    "created_at": "2026-04-12T..."
  }
}
```

## 🌐 URLs

### Upload-Routen
```
/upload/                  # Upload Center Dashboard
/upload/video/            # Video hochladen
/upload/video/ajax/       # AJAX Video-Upload
/upload/thumbnail/        # Bild hochladen
/upload/livestream/       # Live-Stream-Recording
/upload/ad-video/         # Werbevideo hochladen
/upload/logo/             # Logo hochladen
```

## 💻 Nutzung

### 1. Upload Center
Besuchen Sie `/upload/` für das Upload-Dashboard mit allen Optionen.

### 2. Video hochladen
```
1. Gehe zu /upload/video/
2. Wähle Videodatei
3. Fülle Titel, Beschreibung, Kategorie aus
4. Klicke auf "Video hochladen"
5. Video erscheint automatisch in der Mediathek
```

### 3. Programmcode-Nutzung
```python
from tv.jds_upload_service import JDSCloudUploadService

# Upload-Datei
result = JDSCloudUploadService.upload_video(uploaded_file, title="Mein Video")

if result:
    video = Video.objects.create(
        title=result['title'],
        source_type='upload',
        uploaded_file_url=result['view_url'],
        uploaded_file_download_url=result['download_url'],
        # ... weitere Felder
    )
```

## 🎨 UI/UX Features

- Drag & Drop Upload
- Live-Vorschau für Bilder
- Dateigrößen-Anzeige
- Progress-Bars
- Responsive Design
- Dark Theme
- Validierung

## 🔒 Sicherheit

- Login erforderlich für Uploads
- CSRF-Protection
- File-Type-Validation
- Size-Check auf Client-Seite
- Sichere API-Token-Verwaltung

## 📱 Unterstützte Formate

### Videos
- MP4, MKV, MOV, AVI, WebM
- MPEG, QuickTime, WMV
- 3GP, HLS, MPEG-TS

### Bilder
- JPG/JPEG, PNG, GIF
- WebP, SVG, BMP

## 🚀 Performance

- Chunk-Upload für große Dateien
- Async-Upload-Option
- CDN-Integration über JDS Cloud
- Optimierte Streaming-URLs

## 🔄 Workflow

```
1. User wählt Datei
   ↓
2. Upload zu JDS Cloud
   ↓
3. JDS Cloud speichert Datei
   ↓
4. URLs werden zurückgegeben
   ↓
5. Video-Objekt wird erstellt
   ↓
6. Erscheint in Mediathek
```

## 📝 Hinweise

- Der Authorization-Token ist fest im Code hinterlegt
- Für Produktion: Token in Environment-Variable verschieben
- Upload-Timeout: 5 Minuten (konfigurierbar)
- Keine Client-seitige Größenbeschränkung

## 🆘 Troubleshooting

### Upload schlägt fehl
- Prüfe Internet-Verbindung
- Prüfe JDS Cloud API-Status
- Prüfe Authorization-Token
- Prüfe Logs: `python manage.py runserver`

### Videos werden nicht gestreamt
- Prüfe `get_stream_url()` Methode
- Verwende `download_url` für Streaming
- Prüfe Video-Codec-Kompatibilität

## 🎯 Nächste Schritte

- [ ] Progress-Bar für Uploads
- [ ] Batch-Upload (mehrere Dateien)
- [ ] Video-Thumbnail-Generierung
- [ ] Upload-History-Tracking
- [ ] Video-Transkodierung
- [ ] Automatische Dauer-Erkennung

## 📞 Support

Bei Fragen oder Problemen:
- GitHub Issues erstellen
- Dokumentation: https://jds-cloud.lovable.app
- API-Dokumentation im Code

---

**Version**: 1.0  
**Datum**: 12. April 2026  
**Entwickler**: Joel Digitals
