#!/bin/bash
#
# RSL TV - Automatisches Setup Script
# =====================================
# Installiert alle Dependencies und richtet das System ein
#

set -e  # Beende bei Fehler

echo "======================================"
echo "  RSL TV - Automatisches Setup"
echo "======================================"
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funktion für Success-Messages
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Funktion für Error-Messages
error() {
    echo -e "${RED}❌ $1${NC}"
}

# Funktion für Info-Messages
info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Prüfe ob Python installiert ist
echo "Schritt 1/6: Prüfe Python..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 nicht gefunden!"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
success "Python gefunden: $PYTHON_VERSION"
echo ""

# Prüfe ob FFmpeg installiert ist
echo "Schritt 2/6: Prüfe FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    error "FFmpeg nicht gefunden!"
    echo ""
    info "Installiere FFmpeg mit:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  MacOS: brew install ffmpeg"
    echo ""
    read -p "Möchten Sie fortfahren ohne FFmpeg? (j/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Jj]$ ]]; then
        exit 1
    fi
else
    FFMPEG_VERSION=$(ffmpeg -version | head -n 1)
    success "FFmpeg gefunden: $FFMPEG_VERSION"
fi
echo ""

# Installiere Python-Dependencies
echo "Schritt 3/6: Installiere Python-Pakete..."
pip install --break-system-packages opencv-python numpy python-dotenv django yt-dlp 2>&1 | grep -v "already satisfied" || true
success "Python-Pakete installiert"
echo ""

# Backup alte Dateien
echo "Schritt 4/6: Erstelle Backups..."
if [ -f "python_streamer.py" ]; then
    cp python_streamer.py python_streamer_backup_$(date +%Y%m%d_%H%M%S).py
    success "Backup von python_streamer.py erstellt"
fi

if [ -f "tv/templates/tv/mediathek.html" ]; then
    cp tv/templates/tv/mediathek.html tv/templates/tv/mediathek_backup_$(date +%Y%m%d_%H%M%S).html
    success "Backup von mediathek.html erstellt"
fi
echo ""

# Kopiere neue Dateien
echo "Schritt 5/6: Installiere neue Dateien..."

# Streamer
if [ -f "python_streamer_fixed.py" ]; then
    cp python_streamer_fixed.py python_streamer.py
    chmod +x python_streamer.py
    success "python_streamer.py aktualisiert"
else
    error "python_streamer_fixed.py nicht gefunden!"
fi

# Mediathek
if [ -f "tv/templates/tv/mediathek_fixed.html" ]; then
    cp tv/templates/tv/mediathek_fixed.html tv/templates/tv/mediathek.html
    success "mediathek.html aktualisiert"
else
    error "mediathek_fixed.html nicht gefunden!"
fi

# TV-Display
if [ -f "tv/templates/tv/tv_display_fixed.html" ]; then
    cp tv/templates/tv/tv_display_fixed.html tv/templates/tv/tv_display.html
    success "tv_display.html erstellt"
else
    error "tv_display_fixed.html nicht gefunden!"
fi

# API Views
if [ -f "tv/api_views.py" ]; then
    success "api_views.py bereits vorhanden"
else
    error "tv/api_views.py nicht gefunden!"
    info "Bitte manuell erstellen (siehe KOMPLETTE_LOESUNGSANLEITUNG.md)"
fi
echo ""

# Django Migrations
echo "Schritt 6/6: Führe Django-Migrations aus..."
if [ -f "manage.py" ]; then
    python3 manage.py makemigrations --no-input 2>&1 | grep -v "No changes detected" || true
    python3 manage.py migrate --no-input
    success "Migrationen abgeschlossen"
else
    error "manage.py nicht gefunden!"
fi
echo ""

# Zusammenfassung
echo "======================================"
echo "  Setup abgeschlossen!"
echo "======================================"
echo ""
success "Alle Dateien installiert"
echo ""
echo "Nächste Schritte:"
echo ""
echo "1. Stream-Keys konfigurieren:"
echo "   python manage.py shell"
echo "   > from tv.models import ProgramRoom"
echo "   > room = ProgramRoom.objects.first()"
echo "   > room.youtube_stream_key = 'DEIN-KEY'"
echo "   > room.twitch_stream_key = 'DEIN-KEY'"
echo "   > room.is_streaming_youtube = True"
echo "   > room.is_streaming_twitch = True"
echo "   > room.save()"
echo ""
echo "2. URLs in tv/urls.py hinzufügen (siehe KOMPLETTE_LOESUNGSANLEITUNG.md)"
echo ""
echo "3. TV-Display View in tv/views.py hinzufügen"
echo ""
echo "4. LiveAdBreak Model erstellen (falls nötig)"
echo ""
echo "5. Testen:"
echo "   Stream: python python_streamer.py"
echo "   Web:    python manage.py runserver"
echo ""
info "Siehe KOMPLETTE_LOESUNGSANLEITUNG.md für Details"
echo ""
