"""
RSL TV – Models (vereinigt)
Kombiniert: Basis-System + Erweiterte Features (Audio, Multi-Kamera, Übergänge, Replay)
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import os


# ══════════════════════════════════════════════════════════════════════════════
# BASIS-MODELLE (aus Datei 1)
# ══════════════════════════════════════════════════════════════════════════════

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    color = models.CharField(max_length=7, default='#e63946')

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"

    def __str__(self):
        return self.name


class SenderLogo(models.Model):
    """Hochgeladenes RSL-Logo für Wasserzeichen im Stream"""
    POSITION_CHOICES = [
        ('top_left', 'Oben Links'),
        ('top_right', 'Oben Rechts'),
        ('bottom_left', 'Unten Links'),
        ('bottom_right', 'Unten Rechts'),
    ]
    logo = models.ImageField(upload_to='logo/', verbose_name="Logo-Datei (PNG mit Transparenz empfohlen)")
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='top_right')
    opacity = models.FloatField(default=0.85, help_text="Deckkraft 0.0 – 1.0")
    scale = models.IntegerField(default=80, help_text="Breite in Pixel")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sender-Logo"
        verbose_name_plural = "Sender-Logo"

    def __str__(self):
        return f"RSL Logo ({self.get_position_display()})"

    def get_ffmpeg_overlay(self):
        """Gibt den FFmpeg overlay-Filter zurück"""
        path = self.logo.path
        scale = self.scale
        op = self.opacity

        pos_map = {
            'top_left':     f"overlay=10:10",
            'top_right':    f"overlay=W-w-10:10",
            'bottom_left':  f"overlay=10:H-h-10",
            'bottom_right': f"overlay=W-w-10:H-h-10",
        }
        overlay = pos_map.get(self.position, "overlay=W-w-10:10")
        return {
            'logo_path': path,
            'scale': scale,
            'opacity': op,
            'overlay': overlay,
        }


class Video(models.Model):
    SOURCE_CHOICES = [
        ('youtube', 'YouTube'),
        ('gdrive', 'Google Drive'),
        ('dropbox', 'Dropbox'),
        ('direct', 'Direkt-URL'),
        ('twitch', 'Twitch VOD'),
        ('upload', 'Hochgeladene Datei'),  # NEU: Für echte Uploads
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='youtube')
    source_url = models.URLField(max_length=500, blank=True)  # Jetzt optional für Uploads
    
    # NEU: Felder für echte Datei-Uploads
    uploaded_file_id = models.CharField(max_length=255, blank=True, help_text="JDS Cloud File ID")
    uploaded_file_url = models.URLField(max_length=1000, blank=True, help_text="JDS Cloud View URL")
    uploaded_file_download_url = models.URLField(max_length=1000, blank=True, help_text="JDS Cloud Download URL")
    uploaded_file_name = models.CharField(max_length=500, blank=True, help_text="Original Dateiname")
    uploaded_file_size = models.BigIntegerField(default=0, help_text="Dateigröße in Bytes")
    uploaded_file_type = models.CharField(max_length=100, blank=True, help_text="MIME Type")
    
    thumbnail_url = models.URLField(blank=True)
    duration = models.IntegerField(default=0, help_text="Sekunden")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    allow_in_mediathek = models.BooleanField(default=True, help_text="In Mediathek anzeigen? Wenn nein, nur im Stream spielbar")
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Videos"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def duration_display(self):
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def get_stream_url(self):
        # NEU: Wenn es ein Upload ist, verwende die Download-URL
        if self.source_type == 'upload' and self.uploaded_file_download_url:
            return self.uploaded_file_download_url
        elif self.source_type == 'gdrive' and 'drive.google.com/file/d/' in self.source_url:
            file_id = self.source_url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        elif self.source_type == 'dropbox':
            return self.source_url.replace('?dl=0', '?dl=1')
        return self.source_url


class AdVideo(models.Model):
    """
    Werbevideo-Pool: Trailer-Werbung, normale Werbung, Abspann-Werbung.
    Werden automatisch zu Werbeblöcken zusammengestellt.
    """
    TYPE_CHOICES = [
        ('trailer', 'Werbe-Trailer (Sendeankündigung, vor Block)'),
        ('spot',    'Werbespot (Hauptwerbung)'),
        ('outro',   'Werbe-Outro (Abschluss, nach Block)'),
    ]

    title = models.CharField(max_length=255)
    video_url = models.URLField(max_length=500)
    duration = models.IntegerField(default=30, help_text="Sekunden")
    ad_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='spot')
    is_active = models.BooleanField(default=True)
    advertisement = models.ForeignKey(
        'Advertisement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ad_videos'
    )

    class Meta:
        verbose_name = "Werbevideo"
        verbose_name_plural = "Werbevideos"

    def __str__(self):
        return f"[{self.get_ad_type_display()}] {self.title}"


class AdBreakTemplate(models.Model):
    """
    Vorlage für einen Werbeblock.
    Definiert wie lange ein Block dauern soll – System füllt ihn automatisch.
    """
    name = models.CharField(max_length=100, default="Standard-Werbeblock")
    max_duration = models.IntegerField(default=180, help_text="Maximale Blockdauer in Sekunden")
    include_trailer = models.BooleanField(default=True, help_text="Werbe-Trailer zu Beginn des Blocks")
    include_outro = models.BooleanField(default=True, help_text="Werbe-Outro am Ende des Blocks")

    class Meta:
        verbose_name = "Werbeblock-Vorlage"
        verbose_name_plural = "Werbeblock-Vorlagen"

    def __str__(self):
        return f"{self.name} (max. {self.max_duration}s)"

    def build_block(self):
        """
        Stellt automatisch einen Werbeblock zusammen:
        [Trailer] + [Spots bis max_duration gefüllt] + [Outro]
        Gibt eine Liste von AdVideo-Objekten zurück.
        """
        result = []
        used_seconds = 0

        # 1. Trailer
        if self.include_trailer:
            trailers = list(AdVideo.objects.filter(ad_type='trailer', is_active=True))
            import random
            if trailers:
                t = random.choice(trailers)
                result.append(t)
                used_seconds += t.duration

        # 2. Aktive Werbespots
        now = timezone.now()
        spots = list(AdVideo.objects.filter(
            ad_type='spot',
            is_active=True,
        ).filter(
            models.Q(advertisement__isnull=True) |
            models.Q(
                advertisement__status='active',
                advertisement__paid=True,
                advertisement__start_date__lte=now.date(),
                advertisement__end_date__gte=now.date(),
            )
        ).order_by('?'))

        for spot in spots:
            if used_seconds + spot.duration <= self.max_duration - (30 if self.include_outro else 0):
                result.append(spot)
                used_seconds += spot.duration
            if used_seconds >= self.max_duration:
                break

        # 3. Outro
        if self.include_outro:
            outros = list(AdVideo.objects.filter(ad_type='outro', is_active=True))
            import random
            if outros:
                o = random.choice(outros)
                result.append(o)

        return result


class AdBreak(models.Model):
    """
    Geplante Werbepause – wird einem Schedule-Eintrag zugeordnet.
    Das Video wird an dieser Stelle PAUSIERT.
    """
    schedule = models.ForeignKey('Schedule', on_delete=models.CASCADE, related_name='ad_breaks')
    time_offset_seconds = models.IntegerField(
        help_text="Zeitpunkt in Sekunden nach Sendungsbeginn (0 = sofort am Anfang)"
    )
    template = models.ForeignKey(
        AdBreakTemplate, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Werbeblock-Vorlage"
    )
    max_duration = models.IntegerField(default=180, help_text="Maximale Dauer in Sekunden")
    played = models.BooleanField(default=False)
    played_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Geplante Werbepause"
        verbose_name_plural = "Geplante Werbepausen"
        ordering = ['time_offset_seconds']

    def __str__(self):
        m, s = divmod(self.time_offset_seconds, 60)
        return f"Werbepause nach {m}:{s:02d} in '{self.schedule.title}'"

    def get_block(self):
        """Holt oder erstellt den Werbeblock"""
        if self.template:
            return self.template.build_block()
        # Fallback: Standard-Block
        default = AdBreakTemplate(
            max_duration=self.max_duration,
            include_trailer=True,
            include_outro=True
        )
        return default.build_block()


class LiveAdBreak(models.Model):
    """
    Manuell ausgelöste Werbepause bei Live-Sendungen.
    Wird über den Admin-Button gestartet/gestoppt.
    """
    live_stream = models.ForeignKey('LiveStream', on_delete=models.CASCADE, related_name='ad_breaks')
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    template = models.ForeignKey(AdBreakTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    max_duration = models.IntegerField(default=180)

    class Meta:
        verbose_name = "Live-Werbepause"
        verbose_name_plural = "Live-Werbepausen"

    def __str__(self):
        status = "AKTIV" if self.is_active else "Beendet"
        return f"[{status}] Werbepause in {self.live_stream.title}"

    def start(self):
        self.is_active = True
        self.started_at = timezone.now()
        self.ended_at = None
        self.save()

    def stop(self):
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()


class Schedule(models.Model):
    REPEAT_CHOICES = [
        ('none', 'Keine Wiederholung'),
        ('daily', 'Täglich'),
        ('weekly', 'Wöchentlich'),
        ('weekdays', 'Mo–Fr'),
        ('weekends', 'Sa–So'),
    ]

    title = models.CharField(max_length=255)
    video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, blank=True)
    live_stream = models.ForeignKey('LiveStream', on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    repeat = models.CharField(max_length=20, choices=REPEAT_CHOICES, default='none')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sendeplan-Eintrag"
        verbose_name_plural = "Sendeplan"
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time.strftime('%d.%m %H:%M')} – {self.title}"

    def duration_minutes(self):
        return int((self.end_time - self.start_time).total_seconds() / 60)


class LiveStream(models.Model):
    SOURCE_CHOICES = [
        ('youtube', 'YouTube Live'),
        ('twitch', 'Twitch'),
        ('rtmp', 'RTMP (OBS/extern)'),
        ('hls', 'HLS Stream'),
        ('iframe', 'iFrame/Embed'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='youtube')
    stream_url = models.URLField(max_length=500)
    embed_url = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(blank=True)
    is_live = models.BooleanField(default=False, verbose_name="Gerade Live")
    scheduled_start = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Live-Stream"
        verbose_name_plural = "Live-Streams"

    def __str__(self):
        return ("🔴 LIVE – " if self.is_live else "") + self.title

    def get_embed_url(self):
        if self.embed_url:
            return self.embed_url
        if self.source_type == 'youtube':
            if 'watch?v=' in self.stream_url:
                vid = self.stream_url.split('watch?v=')[1].split('&')[0]
                return f"https://www.youtube.com/embed/{vid}?autoplay=1"
            elif 'youtu.be/' in self.stream_url:
                vid = self.stream_url.split('youtu.be/')[1]
                return f"https://www.youtube.com/embed/{vid}?autoplay=1"
        elif self.source_type == 'twitch':
            channel = self.stream_url.split('twitch.tv/')[-1].strip('/')
            return f"https://player.twitch.tv/?channel={channel}&parent=localhost"
        return self.stream_url

    def has_active_ad_break(self):
        return self.ad_breaks.filter(is_active=True).exists()

    def get_active_ad_break(self):
        return self.ad_breaks.filter(is_active=True).first()


class Advertisement(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ausstehend (Zahlung offen)'),
        ('invoice_sent', 'Rechnung versendet'),
        ('paid', 'Bezahlt – Wartet auf Freischaltung'),
        ('active', 'Aktiv (läuft auf RSL)'),
        ('expired', 'Abgelaufen'),
        ('rejected', 'Abgelehnt'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    video_url = models.URLField(max_length=500)
    title = models.CharField(max_length=255)
    duration = models.IntegerField(default=30)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid = models.BooleanField(default=False)
    plays_count = models.IntegerField(default=0)
    max_plays = models.IntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    TIMESLOT_CHOICES = [
        ('all', 'Ganztägig'),
        ('morning', 'Morgen (06–12 Uhr)'),
        ('midday', 'Mittag (12–18 Uhr)'),
        ('evening', 'Abend (18–23 Uhr)'),
        ('night', 'Nacht (23–06 Uhr)'),
    ]
    timeslot = models.CharField(max_length=20, choices=TIMESLOT_CHOICES, default='all')

    class Meta:
        verbose_name = "Werbung"
        verbose_name_plural = "Werbeanzeigen"

    def __str__(self):
        return f"{self.company_name} – {self.title} [{self.get_status_display()}]"

    def is_currently_active(self):
        now = timezone.now().date()
        return (
            self.status == 'active' and self.paid and
            self.start_date <= now <= self.end_date and
            self.plays_count < self.max_plays
        )


class AdBooking(models.Model):
    PACKAGE_CHOICES = [
        ('starter',   'Starter – 49€ (50 Einblendungen)'),
        ('basic',     'Basic – 99€ (150 Einblendungen)'),
        ('standard',  'Standard – 199€ (400 Einblendungen)'),
        ('premium',   'Premium – 399€ (1000 Einblendungen)'),
        ('exclusive', 'Exklusiv – auf Anfrage'),
    ]

    PACKAGE_PRICES = {
        'starter': 49,
        'basic': 99,
        'standard': 199,
        'premium': 399,
        'exclusive': 0,
    }

    PACKAGE_PLAYS = {
        'starter': 50,
        'basic': 150,
        'standard': 400,
        'premium': 1000,
        'exclusive': 9999,
    }

    TIMESLOT_CHOICES = Advertisement.TIMESLOT_CHOICES

    advertisement = models.OneToOneField(Advertisement, on_delete=models.CASCADE, null=True, blank=True)
    package = models.CharField(max_length=20, choices=PACKAGE_CHOICES)
    customer_name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    message = models.TextField(blank=True)
    video_url = models.URLField(max_length=500, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    timeslot = models.CharField(max_length=20, choices=TIMESLOT_CHOICES, default='all')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    invoice_sent = models.BooleanField(default=False)
    booking_confirmation_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Werbebuchung"
        verbose_name_plural = "Werbebuchungen"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} – {self.get_package_display()}"

    def save(self, *args, **kwargs):
        if not self.price and self.package in self.PACKAGE_PRICES:
            self.price = self.PACKAGE_PRICES[self.package]
        super().save(*args, **kwargs)

    @property
    def price_net(self):
        return round(float(self.price) / 1.19, 2)

    @property
    def price_vat(self):
        return round(float(self.price) - self.price_net, 2)

    def get_timeslot_display(self):
        return dict(self.TIMESLOT_CHOICES).get(self.timeslot, self.timeslot)

    def activate_advertisement(self):
        """Erstellt/aktualisiert den Advertisement-Eintrag und schaltet ihn frei"""
        plays = self.PACKAGE_PLAYS.get(self.package, 100)
        if self.advertisement:
            ad = self.advertisement
            ad.status = 'active'
            ad.paid = True
            ad.save()
        else:
            ad = Advertisement.objects.create(
                customer_name=self.customer_name,
                company_name=self.company_name,
                email=self.email,
                phone=self.phone,
                video_url=self.video_url,
                title=f"Werbung: {self.company_name}",
                duration=30,
                start_date=self.start_date,
                end_date=self.end_date,
                status='active',
                paid=True,
                max_plays=plays,
                timeslot=self.timeslot,
            )
            # AdVideo anlegen
            AdVideo.objects.create(
                title=f"Spot: {self.company_name}",
                video_url=self.video_url,
                duration=30,
                ad_type='spot',
                advertisement=ad,
            )
            self.advertisement = ad
        self.paid = True
        self.save()
        return ad


class PlaylistItem(models.Model):
    name = models.CharField(max_length=255)
    videos = models.ManyToManyField(Video, through='PlaylistEntry')
    play_mode = models.CharField(max_length=20, choices=[('sequential', 'Sequenziell'), ('random', 'Zufällig')], default='sequential')
    is_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Playlist"

    def __str__(self):
        return self.name


class PlaylistEntry(models.Model):
    playlist = models.ForeignKey(PlaylistItem, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']


class NewsItem(models.Model):
    text = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Laufschrift-News"
        ordering = ['-created_at']

    def __str__(self):
        return self.text[:80]


class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Kontaktnachricht"

    def __str__(self):
        return f"{self.name} – {self.subject}"


class StandbyImage(models.Model):
    """Pausenbild für Sendepausen (außerhalb von Sendungen)"""
    title = models.CharField(max_length=200, default="Pausenbild")
    image = models.ImageField(upload_to='standby/', verbose_name="Pausenbild (16:9 Format empfohlen)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Pausenbild"
        verbose_name_plural = "Pausenbilder"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


# ══════════════════════════════════════════════════════════════════════════════
# ERWEITERTES KAMERA- & AUDIO-SYSTEM (aus Datei 2 - erweitert)
# ══════════════════════════════════════════════════════════════════════════════

class AudioSource(models.Model):
    """Audio-Quelle (Kamera-Ton, PC-Audio, externes Mikro, etc.)"""
    AUDIO_TYPE_CHOICES = [
        ('camera', 'Kamera-Ton'),
        ('pc', 'PC-Audio'),
        ('microphone', 'Mikrofon'),
        ('line_in', 'Line-In'),
        ('virtual', 'Virtuelles Audio'),
        ('file', 'Audio-Datei'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Bezeichnung")
    audio_type = models.CharField(max_length=20, choices=AUDIO_TYPE_CHOICES)
    source_url = models.CharField(max_length=500, blank=True, help_text="RTSP/RTMP/HTTP URL oder Geräte-Pfad")
    audio_file = models.FileField(upload_to='audio/', blank=True, null=True)
    
    # Audio-Eigenschaften
    volume = models.IntegerField(default=100, validators=[MinValueValidator(0), MaxValueValidator(200)])
    is_muted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_looping = models.BooleanField(default=False, help_text="Endlos wiederholen (z.B. für Hintergrundmusik)")
    
    # Linked Camera (wenn Kamera-Ton)
    linked_camera = models.ForeignKey('Camera', on_delete=models.CASCADE, null=True, blank=True, related_name='audio_sources')
    
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.IntegerField(default=0, help_text="Reihenfolge im Mixer")
    
    class Meta:
        verbose_name = "Audio-Quelle"
        verbose_name_plural = "Audio-Quellen"
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_audio_type_display()})"
    
    def get_audio_url(self):
        """Gibt die tatsächliche Audio-URL zurück"""
        if self.audio_file:
            return self.audio_file.path
        if self.linked_camera and self.audio_type == 'camera':
            return self.linked_camera.stream_url
        return self.source_url or ''


class Camera(models.Model):
    """Erweiterte Kamera mit Audio-Support und FFmpeg-Integration"""
    CAMERA_TYPE_CHOICES = [
        ('rtsp', 'RTSP (IP-Kamera)'),
        ('rtmp', 'RTMP (Stream)'),
        ('http', 'HTTP (MJPEG/HLS)'),
        ('webcam', 'Webcam (lokal)'),
        ('ndi', 'NDI'),
        ('sdi', 'SDI/HDMI'),
        ('virtual', 'Virtuell (OBS Virtual Camera)'),
        ('screen', 'Bildschirm-Capture'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Kamera-Name")
    camera_type = models.CharField(
        max_length=20,
        choices=CAMERA_TYPE_CHOICES,
        default='rtsp'
    )
    stream_url = models.CharField(max_length=500, help_text="Stream-URL oder Geräte-Pfad (z.B. /dev/video0)")
    
    # Preview
    preview_image = models.ImageField(upload_to='camera_previews/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Audio-Einstellungen
    has_audio = models.BooleanField(default=True)
    audio_enabled = models.BooleanField(default=False, help_text="Kamera-Audio verwenden")
    
    # Position im Regieraum
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Kamera"
        verbose_name_plural = "Kameras"
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_camera_type_display()})"
    
    def get_ffmpeg_input(self):
        """Generiert FFmpeg-Input-Parameter für diese Kamera"""
        params = []
        
        if self.camera_type == 'rtsp':
            params = ['-rtsp_transport', 'tcp', '-i', self.stream_url]
        elif self.camera_type == 'rtmp':
            params = ['-i', self.stream_url]
        elif self.camera_type == 'webcam':
            params = ['-f', 'v4l2', '-i', self.stream_url]
        elif self.camera_type == 'screen':
            params = ['-f', 'x11grab', '-i', self.stream_url or ':0.0']
        elif self.camera_type == 'ndi':
            params = ['-f', 'libndi_newtek', '-i', self.stream_url]
        else:
            params = ['-i', self.stream_url]
        
        return params


# ══════════════════════════════════════════════════════════════════════════════
# ÜBERGANGS-STUDIO & SZENEN
# ══════════════════════════════════════════════════════════════════════════════

class Transition(models.Model):
    """Übergangseffekt zwischen Szenen/Kameras"""
    TRANSITION_TYPE_CHOICES = [
        ('cut', 'Harter Schnitt'),
        ('fade', 'Überblendung'),
        ('wipe_left', 'Wipe Left'),
        ('wipe_right', 'Wipe Right'),
        ('wipe_up', 'Wipe Up'),
        ('wipe_down', 'Wipe Down'),
        ('dissolve', 'Dissolve'),
        ('slide_left', 'Slide Left'),
        ('slide_right', 'Slide Right'),
        ('zoom_in', 'Zoom In'),
        ('zoom_out', 'Zoom Out'),
        ('pixelize', 'Pixelize'),
    ]
    
    name = models.CharField(max_length=100)
    transition_type = models.CharField(max_length=20, choices=TRANSITION_TYPE_CHOICES)
    duration = models.FloatField(default=1.0, help_text="Dauer in Sekunden")
    
    # FFmpeg-Filter
    ffmpeg_filter = models.TextField(blank=True, help_text="Custom FFmpeg xfade Filter")
    
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Übergangseffekt"
        verbose_name_plural = "Übergangseffekte"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.duration}s)"
    
    def get_ffmpeg_filter(self):
        """Gibt FFmpeg xfade Filter zurück"""
        if self.ffmpeg_filter:
            return self.ffmpeg_filter
        
        return f"xfade=transition={self.transition_type}:duration={self.duration}:offset=0"


class Scene(models.Model):
    """Szene im Übergangs-Studio (Kombination aus Kamera + Overlays + Audio)"""
    name = models.CharField(max_length=100)
    
    # Primäre Kamera
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='scenes')
    
    # Audio-Mix für diese Szene
    audio_sources = models.ManyToManyField(AudioSource, blank=True, through='SceneAudioMix')
    
    # Overlays (Lower-Third, Bauchbinde, etc.)
    overlay_text = models.CharField(max_length=500, blank=True)
    overlay_image = models.ImageField(upload_to='overlays/', blank=True, null=True)
    
    # Farb-Korrektur
    brightness = models.IntegerField(default=0, validators=[MinValueValidator(-100), MaxValueValidator(100)])
    contrast = models.IntegerField(default=0, validators=[MinValueValidator(-100), MaxValueValidator(100)])
    saturation = models.IntegerField(default=0, validators=[MinValueValidator(-100), MaxValueValidator(100)])
    
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Szene"
        verbose_name_plural = "Szenen"
        ordering = ['order', 'name']
    
    def __str__(self):
        return f"{self.name} (Kamera: {self.camera.name})"


class SceneAudioMix(models.Model):
    """Audio-Mix für eine Szene"""
    scene = models.ForeignKey(Scene, on_delete=models.CASCADE)
    audio_source = models.ForeignKey(AudioSource, on_delete=models.CASCADE)
    volume = models.IntegerField(default=100, validators=[MinValueValidator(0), MaxValueValidator(200)])
    is_muted = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Szenen-Audio-Mix"
        verbose_name_plural = "Szenen-Audio-Mixe"
        unique_together = ['scene', 'audio_source']


# ══════════════════════════════════════════════════════════════════════════════
# BEITRAGS-PLANUNG & RUNDOWN
# ══════════════════════════════════════════════════════════════════════════════

class ShowRundown(models.Model):
    """Sendeablauf / Rundown für eine Show"""
    title = models.CharField(max_length=200)
    show_date = models.DateTimeField()
    
    # Gesamt-Dauer
    total_planned_duration = models.IntegerField(default=0, help_text="Summe aller Segmente")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_live = models.BooleanField(default=False, help_text="Wird gerade gesendet?")
    
    # Aktuelles Segment
    current_segment = models.ForeignKey('ContentSegment', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_in_rundown')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Show-Rundown"
        verbose_name_plural = "Show-Rundowns"
        ordering = ['-show_date']
    
    def __str__(self):
        return f"{self.title} ({self.show_date.strftime('%d.%m.%Y %H:%M')})"
    
    def calculate_total_duration(self):
        """Berechnet Gesamt-Dauer"""
        total = self.segments.aggregate(models.Sum('planned_duration'))['planned_duration__sum'] or 0
        self.total_planned_duration = total
        self.save(update_fields=['total_planned_duration'])
        return total


class ContentSegment(models.Model):
    """Vorbereiteter Beitrag/Segment für Live-Show"""
    SEGMENT_TYPE_CHOICES = [
        ('video', 'Video-Beitrag'),
        ('interview', 'Interview'),
        ('discussion', 'Diskussion'),
        ('presentation', 'Präsentation'),
        ('game', 'Spiel/Quiz'),
        ('music', 'Musik'),
        ('ad_break', 'Werbepause'),
        ('other', 'Sonstiges'),
    ]
    
    title = models.CharField(max_length=200)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Timing
    planned_duration = models.IntegerField(help_text="Geplante Dauer in Sekunden")
    actual_duration = models.IntegerField(null=True, blank=True, help_text="Tatsächliche Dauer nach Ausstrahlung")
    
    # Content
    video_file = models.FileField(upload_to='segments/', blank=True, null=True)
    video_url = models.URLField(blank=True, max_length=500)
    
    # Szenen-Zuordnung (falls live mit Kamera)
    scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Skript/Notizen
    script = models.TextField(blank=True, help_text="Skript oder Moderations-Text")
    notes = models.TextField(blank=True, help_text="Technische Notizen")
    
    # Platzierung in Rundown
    rundown = models.ForeignKey(ShowRundown, on_delete=models.CASCADE, related_name='segments')
    order = models.IntegerField(default=0)
    
    # Status
    is_ready = models.BooleanField(default=False, help_text="Technisch vorbereitet?")
    was_played = models.BooleanField(default=False)
    played_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Content-Segment"
        verbose_name_plural = "Content-Segmente"
        ordering = ['rundown', 'order']
    
    def __str__(self):
        return f"{self.title} ({self.planned_duration}s)"


# ══════════════════════════════════════════════════════════════════════════════
# REPLAY-SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class ReplayClip(models.Model):
    """Aufgenommener Replay-Clip"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Quelle
    source_camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True)
    source_rundown = models.ForeignKey(ShowRundown, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Datei
    video_file = models.FileField(upload_to='replays/')
    thumbnail = models.ImageField(upload_to='replay_thumbs/', blank=True, null=True)
    duration = models.IntegerField(default=0, help_text="Dauer in Sekunden")
    
    # Timing
    recorded_at = models.DateTimeField(auto_now_add=True)
    in_point = models.FloatField(default=0, help_text="Start-Punkt in Sekunden")
    out_point = models.FloatField(default=0, help_text="End-Punkt in Sekunden")
    
    # Playback-Optionen
    playback_speed = models.FloatField(default=1.0, help_text="1.0 = normal, 0.5 = slow-mo, 2.0 = fast")
    
    # Tags/Kategorisierung
    tags = models.CharField(max_length=500, blank=True)
    
    # Status
    is_favorite = models.BooleanField(default=False)
    times_played = models.IntegerField(default=0)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Replay-Clip"
        verbose_name_plural = "Replay-Clips"
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.title} ({self.duration}s)"
    
    def get_effective_duration(self):
        """Gibt die Dauer unter Berücksichtigung der Geschwindigkeit zurück"""
        base_duration = self.out_point - self.in_point if self.out_point > 0 else self.duration
        return base_duration / self.playback_speed if self.playback_speed > 0 else base_duration


class ReplayPlaylist(models.Model):
    """Zusammenstellung von Replay-Clips"""
    name = models.CharField(max_length=200)
    clips = models.ManyToManyField(ReplayClip, through='ReplayPlaylistItem')
    
    # Auto-generiert?
    auto_generated = models.BooleanField(default=False, help_text="Automatisch aus Show generiert?")
    source_rundown = models.ForeignKey(ShowRundown, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Replay-Playlist"
        verbose_name_plural = "Replay-Playlists"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class ReplayPlaylistItem(models.Model):
    """Einzelner Clip in Replay-Playlist"""
    playlist = models.ForeignKey(ReplayPlaylist, on_delete=models.CASCADE)
    clip = models.ForeignKey(ReplayClip, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    
    # Transition zum nächsten Clip
    transition = models.ForeignKey(Transition, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['playlist', 'clip', 'order']


# ══════════════════════════════════════════════════════════════════════════════
# REGIERÄUME (Vereinigt aus beiden Versionen)
# ══════════════════════════════════════════════════════════════════════════════

class DirectorRoom(models.Model):
    """
    Erweiterter Regieraum mit Multi-Kamera + Audio-Mixing + Streaming.
    Vereinigt Funktionen aus beiden Versionen.
    """
    name = models.CharField(max_length=100, default="Hauptregie")
    description = models.TextField(blank=True)
    
    # Kameras (Many-to-Many für Multi-Kamera-Support)
    cameras = models.ManyToManyField(Camera, blank=True, related_name='director_rooms')
    active_camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name='active_in_rooms')
    preview_camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name='preview_in_rooms')
    
    # Audio-Mixing
    audio_sources = models.ManyToManyField(AudioSource, blank=True, related_name='director_rooms')
    
    # Aktive Szene
    active_scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True, related_name='active_in_rooms')
    
    # Streaming-Konfiguration
    youtube_stream_key = models.CharField(max_length=255, blank=True, help_text="YouTube Stream Key")
    twitch_stream_key = models.CharField(max_length=255, blank=True, help_text="Twitch Stream Key")
    
    # Streaming-Status
    is_streaming_youtube = models.BooleanField(default=False)
    is_streaming_twitch = models.BooleanField(default=False)
    is_streaming = models.BooleanField(default=False, help_text="Wird aktuell gestreamt?")
    current_output = models.TextField(blank=True, help_text="Aktuelle Stream-URL oder Status")
    
    # Recording
    is_recording = models.BooleanField(default=False)
    recording_path = models.CharField(max_length=500, blank=True)
    
    # Prozess-Management
    ffmpeg_pid = models.IntegerField(null=True, blank=True, help_text="Prozess-ID des laufenden FFmpeg")
    last_stream_started = models.DateTimeField(null=True, blank=True)
    
    # Automatische Replay-Aufnahme
    auto_record_replays = models.BooleanField(default=True, help_text="Automatisch Replay-Clips erstellen")
    replay_buffer_seconds = models.IntegerField(default=30, help_text="Replay-Puffer in Sekunden")
    
    # Logging
    stream_log = models.TextField(blank=True, help_text="Stream-Log")
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Regieraum"
        verbose_name_plural = "Regieräume"
        ordering = ['name']
    
    def __str__(self):
        status = "🟢" if self.is_streaming else "🔴"
        return f"{status} {self.name}"
    
    def append_log(self, message):
        """Fügt Log-Eintrag hinzu (max 1000 Zeilen)"""
        timestamp = timezone.now().strftime('%H:%M:%S')
        entry = f"[{timestamp}] {message}\n"
        self.stream_log = (self.stream_log or '') + entry
        lines = self.stream_log.split('\n')
        if len(lines) > 1000:
            self.stream_log = '\n'.join(lines[-1000:])
        self.save(update_fields=['stream_log', 'updated_at'])
    
    def get_active_audio_sources(self):
        """Gibt alle aktiven Audio-Quellen zurück"""
        return self.audio_sources.filter(is_active=True, is_muted=False)
    
    def switch_to_camera(self, camera, use_transition=True):
        """Wechselt zur angegebenen Kamera (mit optionalem Übergang)"""
        old_camera = self.active_camera
        
        if use_transition and old_camera and old_camera != camera:
            transition = Transition.objects.filter(is_default=True).first()
            if not transition:
                transition = Transition.objects.filter(is_active=True).first()
            
            if transition:
                self.append_log(f"Übergang: {old_camera.name} → {camera.name} ({transition.name})")
        
        self.active_camera = camera
        self.save(update_fields=['active_camera', 'updated_at'])
        self.append_log(f"Kamera aktiv: {camera.name}")
    
    def create_replay_clip(self, title, duration_seconds=30):
        """Erstellt Replay-Clip aus aktuellem Stream-Buffer"""
        if not self.auto_record_replays:
            return None
        
        clip = ReplayClip.objects.create(
            title=title,
            source_camera=self.active_camera,
            duration=duration_seconds,
        )
        
        self.append_log(f"Replay-Clip erstellt: {title} ({duration_seconds}s)")
        return clip


class DirectorRoomCamera(models.Model):
    """Zuordnung von Kameras zu Regieräumen mit Reihenfolge"""
    room = models.ForeignKey(DirectorRoom, on_delete=models.CASCADE, related_name='room_cameras')
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=False, help_text="Ist diese Kamera aktuell aktiv?")
    
    class Meta:
        verbose_name = "Regieraum-Kamera"
        verbose_name_plural = "Regieraum-Kameras"
        ordering = ['room', 'order']
        unique_together = ['room', 'camera']
    
    def __str__(self):
        active = "🟢" if self.is_active else "⚪"
        return f"{active} {self.room.name} - {self.camera.name}"


# ══════════════════════════════════════════════════════════════════════════════
# LIVE-DIRECTOR (Legacy - für einfache Live-Streams)
# ══════════════════════════════════════════════════════════════════════════════

class LiveDirector(models.Model):
    """Aktuell ausgewählte Kamera für Live-Sendung (Legacy-Einfachversion)"""
    live_stream = models.OneToOneField(LiveStream, on_delete=models.CASCADE, related_name='director')
    selected_camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Live-Regie (Legacy)"

    def __str__(self):
        return f"Regie für {self.live_stream.title}"


# ══════════════════════════════════════════════════════════════════════════════
# PROGRAMM-REGIERAUM (24/7 Streaming)
# ══════════════════════════════════════════════════════════════════════════════

class ProgramRoom(models.Model):
    """
    Programm-Regieraum für 24/7 Sendeplan-Streaming.
    Steuert FFmpeg-Prozesse, Werbepausen und Stream-Status.
    """
    # Primärschlüssel fix auf 1 für Singleton-Pattern
    id = models.AutoField(primary_key=True)
    
    # Stream-Keys und RTMP-URLs
    youtube_stream_key = models.CharField(max_length=255, blank=True, help_text="YouTube Stream Key")
    twitch_stream_key = models.CharField(max_length=255, blank=True, help_text="Twitch Stream Key")
    youtube_rtmp_url = models.CharField(max_length=255, default='rtmp://a.rtmp.youtube.com/live2')
    twitch_rtmp_url = models.CharField(max_length=255, default='rtmp://live.twitch.tv/app')
    
    # Stream-Status
    is_streaming_youtube = models.BooleanField(default=False)
    is_streaming_twitch = models.BooleanField(default=False)
    ffmpeg_pid = models.IntegerField(null=True, blank=True, help_text="Prozess-ID des laufenden FFmpeg")
    
    # Werbepause-Status
    ad_break_active = models.BooleanField(default=False)
    ad_break_started_at = models.DateTimeField(null=True, blank=True)
    ad_break_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Video-Position für Resume nach Werbepause
    video_position_seconds = models.IntegerField(default=0, help_text="Aktuelle Position im Video (Sekunden)")
    
    # Buffer-Konfiguration
    buffer_ahead_minutes = models.IntegerField(default=5, help_text="Minuten vor Sendebeginn für Vorab-Download")
    
    # Logging
    log_text = models.TextField(blank=True, default="", help_text="Letzte Log-Einträge")
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Programm-Regieraum"
        verbose_name_plural = "Programm-Regieraum"

    def __str__(self):
        status = "🟢" if (self.is_streaming_youtube or self.is_streaming_twitch) else "🔴"
        return f"{status} Programm-Regieraum"

    def get_rtmp_targets(self):
        """Gibt Liste der aktiven RTMP-Ziele zurück"""
        targets = []
        if self.youtube_stream_key:
            targets.append(('youtube', f"{self.youtube_rtmp_url}/{self.youtube_stream_key}"))
        if self.twitch_stream_key:
            targets.append(('twitch', f"{self.twitch_rtmp_url}/{self.twitch_stream_key}"))
        return targets

    def append_log(self, message):
        """Fügt Log-Eintrag hinzu (max 100 Zeilen)"""
        timestamp = timezone.now().strftime("%H:%M:%S")
        new_line = f"[{timestamp}] {message}"
        lines = self.log_text.split('\n') if self.log_text else []
        lines.append(new_line)
        self.log_text = '\n'.join(lines[-100:])
        self.save(update_fields=['log_text', 'updated_at'])


class VideoCache(models.Model):
    """
    Lokaler Cache für Videos aus dem Sendeplan.
    Videos werden vorab heruntergeladen, um Buffering zu vermeiden.
    """
    video = models.OneToOneField(Video, on_delete=models.CASCADE, related_name='cache')
    
    STATUS_CHOICES = [
        ('pending', 'Wartet'),
        ('downloading', 'Wird heruntergeladen'),
        ('ready', 'Bereit'),
        ('error', 'Fehler'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    local_path = models.CharField(max_length=500, blank=True, help_text="Lokaler Dateipfad")
    file_size_mb = models.FloatField(default=0)
    duration_seconds = models.IntegerField(default=0)
    progress_percent = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video-Cache"
        verbose_name_plural = "Video-Caches"

    def __str__(self):
        return f"Cache: {self.video.title} ({self.get_status_display()})"

    def is_ready(self):
        """Prüft ob Video bereit und Datei existiert"""
        if self.status != 'ready':
            return False
        if not self.local_path:
            return False
        import os
        return os.path.exists(self.local_path)


class StreamProcess(models.Model):
    """
    Protokollierung von gestarteten FFmpeg-Stream-Prozessen.
    """
    program_room = models.ForeignKey(ProgramRoom, on_delete=models.CASCADE, related_name='processes')
    
    STATUS_CHOICES = [
        ('starting', 'Wird gestartet'),
        ('running', 'Läuft'),
        ('stopped', 'Gestoppt'),
        ('error', 'Fehler'),
        ('crashed', 'Abgestürzt'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='starting')
    pid = models.IntegerField(null=True, blank=True)
    platforms = models.CharField(max_length=100, help_text="youtube, twitch, both")
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    log_output = models.TextField(blank=True)

    class Meta:
        verbose_name = "Stream-Prozess"
        verbose_name_plural = "Stream-Prozesse"
        ordering = ['-started_at']

    def __str__(self):
        return f"Stream {self.pid or 'N/A'} ({self.get_status_display()})"

# Füge dies zu tv/models.py hinzu (am Ende vor den letzten Zeilen)

class PauseScreen(models.Model):
    """Pausenbild für Live-Sendungen"""
    BACKGROUND_TYPE_CHOICES = [
        ('gradient', 'Farbverlauf'),
        ('solid', 'Einfarbig'),
        ('image', 'Bild'),
    ]
    
    ANIMATION_CHOICES = [
        ('none', 'Keine'),
        ('fadeIn', 'Einblenden'),
        ('slideDown', 'Heruntergleiten'),
        ('pulse', 'Pulsieren'),
    ]
    
    title = models.CharField(max_length=200)
    background_type = models.CharField(max_length=20, choices=BACKGROUND_TYPE_CHOICES, default='gradient')
    
    # Farben (für gradient/solid)
    color_primary = models.CharField(max_length=7, default='#e63946', help_text="Hex-Farbe z.B. #e63946")
    color_secondary = models.CharField(max_length=7, default='#c1121f', help_text="Nur für Gradient")
    
    # Bild (optional)
    background_image = models.ImageField(upload_to='pause_screens/', blank=True, null=True)
    
    # Text
    main_text = models.CharField(max_length=100, default='Kurze Pause')
    sub_text = models.CharField(max_length=200, default='Wir sind gleich zurück', blank=True)
    
    # Logo
    show_logo = models.BooleanField(default=True)
    custom_logo = models.ImageField(upload_to='pause_screens/logos/', blank=True, null=True)
    
    # Animation
    animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='none')
    
    # Status
    is_active = models.BooleanField(default=False, help_text="Aktuell verwendetes Pausenbild")
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Pausenbild"
        verbose_name_plural = "Pausenbilder"
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return f"{self.title} {'(AKTIV)' if self.is_active else ''}"
    
    def activate(self):
        """Aktiviert dieses Pausenbild und deaktiviert alle anderen"""
        PauseScreen.objects.all().update(is_active=False)
        self.is_active = True
        self.save()
    
    def get_css_background(self):
        """Gibt den CSS-Background-String zurück"""
        if self.background_type == 'gradient':
            return f"linear-gradient(135deg, {self.color_primary} 0%, {self.color_secondary} 100%)"
        elif self.background_type == 'solid':
            return self.color_primary
        elif self.background_type == 'image' and self.background_image:
            return f"url({self.background_image.url})"
        return "#1a1a1a"


class StreamOverlay(models.Model):
    """Lower-Third und andere Overlays für den Stream"""
    OVERLAY_TYPE_CHOICES = [
        ('lower_third', 'Lower Third (Name/Titel)'),
        ('ticker', 'Lauftext'),
        ('countdown', 'Countdown'),
        ('logo', 'Logo/Bug'),
        ('scoreboard', 'Spielstand'),
    ]
    
    POSITION_CHOICES = [
        ('bottom', 'Unten'),
        ('top', 'Oben'),
        ('left', 'Links'),
        ('right', 'Rechts'),
        ('center', 'Mittig'),
        ('bottom_left', 'Unten Links'),
        ('bottom_right', 'Unten Rechts'),
        ('top_left', 'Oben Links'),
        ('top_right', 'Oben Rechts'),
    ]
    
    name = models.CharField(max_length=200)
    overlay_type = models.CharField(max_length=20, choices=OVERLAY_TYPE_CHOICES)
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='bottom')
    
    # Design
    background_color = models.CharField(max_length=7, default='#e63946')
    text_color = models.CharField(max_length=7, default='#ffffff')
    font_size = models.IntegerField(default=24, help_text="Schriftgröße in Pixel")
    
    # Content
    text_content = models.TextField(help_text="Text für Lower Third oder Ticker")
    duration = models.IntegerField(default=10, help_text="Anzeigedauer in Sekunden (0 = permanent)")
    
    # Animation
    animation_in = models.CharField(max_length=20, default='slideInLeft')
    animation_out = models.CharField(max_length=20, default='slideOutLeft')
    
    # Status
    is_active = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Stream-Overlay"
        verbose_name_plural = "Stream-Overlays"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_overlay_type_display()})"


class CutOutGraphic(models.Model):
    """Cut-Out Grafiken (Freisteller, Sticker, Emojis für Stream)"""
    CATEGORY_CHOICES = [
        ('emoji', 'Emoji/Reaktionen'),
        ('sticker', 'Sticker'),
        ('logo', 'Logo'),
        ('frame', 'Rahmen'),
        ('other', 'Sonstiges'),
    ]
    
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='sticker')
    
    # Bild (PNG mit Transparenz!)
    image = models.ImageField(upload_to='cutouts/', help_text="PNG mit Transparenz empfohlen")
    
    # Position & Größe (Default-Werte)
    default_x = models.IntegerField(default=0, help_text="X-Position in Pixel")
    default_y = models.IntegerField(default=0, help_text="Y-Position in Pixel")
    default_width = models.IntegerField(default=200, help_text="Breite in Pixel")
    default_height = models.IntegerField(default=200, help_text="Höhe in Pixel")
    
    # Verhalten
    can_animate = models.BooleanField(default=False)
    animation_duration = models.IntegerField(default=2, help_text="Dauer in Sekunden")
    
    # Hotkey (optional)
    hotkey = models.CharField(max_length=10, blank=True, help_text="z.B. F1, F2, etc.")
    
    # Status
    is_active = models.BooleanField(default=True)
    times_used = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Cut-Out Grafik"
        verbose_name_plural = "Cut-Out Grafiken"
        ordering = ['-times_used', 'category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    
    def use(self):
        """Zählt Verwendung hoch"""
        self.times_used += 1
        self.save(update_fields=['times_used'])


class StreamPreset(models.Model):
    """Vorkonfigurierte Stream-Einstellungen (wie OBS Profile)"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Video-Einstellungen
    resolution = models.CharField(max_length=20, default='1920x1080')
    fps = models.IntegerField(default=30)
    bitrate = models.IntegerField(default=4500, help_text="Kbps")
    
    # Audio-Einstellungen
    audio_bitrate = models.IntegerField(default=128, help_text="Kbps")
    audio_sample_rate = models.IntegerField(default=48000, help_text="Hz")
    
    # Szenen-Zuordnung
    default_scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Overlays
    overlays = models.ManyToManyField(StreamOverlay, blank=True)
    
    # Status
    is_active = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Stream-Preset"
        verbose_name_plural = "Stream-Presets"
        ordering = ['-is_active', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.resolution}@{self.fps}fps)"
    
    def activate(self):
        """Aktiviert dieses Preset"""
        StreamPreset.objects.all().update(is_active=False)
        self.is_active = True
        self.save()


# ══════════════════════════════════════════════════════════════════════════════
# SERIEN-SYSTEM (Series, Seasons, Episodes)
# ══════════════════════════════════════════════════════════════════════════════

class Series(models.Model):
    """TV-Serie mit mehreren Staffeln"""
    title = models.CharField(max_length=255, verbose_name="Serientitel")
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    poster_url = models.URLField(blank=True, verbose_name="Poster-Bild")
    banner_url = models.URLField(blank=True, verbose_name="Banner-Bild")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True)
    year = models.IntegerField(null=True, blank=True, verbose_name="Erscheinungsjahr")
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, verbose_name="Bewertung (0-10)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Serie"
        verbose_name_plural = "Serien"
        ordering = ['title']

    def __str__(self):
        return self.title

    def get_seasons_count(self):
        return self.seasons.count()

    def get_episodes_count(self):
        return Episode.objects.filter(season__series=self).count()

    def get_latest_episode(self):
        return Episode.objects.filter(season__series=self).order_by('-created_at').first()


class Season(models.Model):
    """Staffel einer Serie"""
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='seasons')
    season_number = models.IntegerField(verbose_name="Staffel-Nummer")
    title = models.CharField(max_length=255, blank=True, verbose_name="Staffel-Titel")
    description = models.TextField(blank=True)
    poster_url = models.URLField(blank=True)
    year = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Staffel"
        verbose_name_plural = "Staffeln"
        ordering = ['series', 'season_number']
        unique_together = ['series', 'season_number']

    def __str__(self):
        if self.title:
            return f"{self.series.title} - Staffel {self.season_number}: {self.title}"
        return f"{self.series.title} - Staffel {self.season_number}"

    def get_episodes_count(self):
        return self.episodes.count()


class Episode(models.Model):
    """Einzelne Episode einer Staffel"""
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='episodes')
    episode_number = models.IntegerField(verbose_name="Episoden-Nummer")
    title = models.CharField(max_length=255, verbose_name="Episoden-Titel")
    description = models.TextField(blank=True)
    
    # Video-Referenz (kann entweder ein vorhandenes Video oder eigene Upload-Felder sein)
    video = models.ForeignKey(Video, on_delete=models.SET_NULL, null=True, blank=True, related_name='episodes')
    
    # Alternative: Eigene Video-Felder für Episoden
    source_type = models.CharField(max_length=20, choices=Video.SOURCE_CHOICES, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    uploaded_file_id = models.CharField(max_length=255, blank=True)
    uploaded_file_url = models.URLField(max_length=1000, blank=True)
    uploaded_file_download_url = models.URLField(max_length=1000, blank=True)
    uploaded_file_name = models.CharField(max_length=500, blank=True)
    uploaded_file_size = models.BigIntegerField(default=0)
    uploaded_file_type = models.CharField(max_length=100, blank=True)
    
    thumbnail_url = models.URLField(blank=True)
    duration = models.IntegerField(default=0, help_text="Sekunden")
    air_date = models.DateField(null=True, blank=True, verbose_name="Erstausstrahlung")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Episode"
        verbose_name_plural = "Episoden"
        ordering = ['season', 'episode_number']
        unique_together = ['season', 'episode_number']

    def __str__(self):
        return f"{self.season.series.title} S{self.season.season_number:02d}E{self.episode_number:02d} - {self.title}"

    def get_stream_url(self):
        """Gibt die Stream-URL zurück (entweder vom verknüpften Video oder eigene Felder)"""
        if self.video:
            return self.video.get_stream_url()
        
        # Eigene Video-Felder
        if self.source_type == 'upload' and self.uploaded_file_download_url:
            return self.uploaded_file_download_url
        elif self.source_type == 'gdrive' and 'drive.google.com/file/d/' in self.source_url:
            file_id = self.source_url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        elif self.source_type == 'dropbox':
            return self.source_url.replace('?dl=0', '?dl=1')
        return self.source_url

    def duration_display(self):
        """Formatierte Dauer-Anzeige"""
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def get_next_episode(self):
        """Gibt die nächste Episode zurück"""
        # Nächste Episode in dieser Staffel
        next_ep = Episode.objects.filter(
            season=self.season,
            episode_number__gt=self.episode_number,
            is_active=True
        ).order_by('episode_number').first()
        
        if next_ep:
            return next_ep
        
        # Erste Episode der nächsten Staffel
        next_season = Season.objects.filter(
            series=self.season.series,
            season_number__gt=self.season.season_number,
            is_active=True
        ).order_by('season_number').first()
        
        if next_season:
            return Episode.objects.filter(
                season=next_season,
                is_active=True
            ).order_by('episode_number').first()
        
        return None

    def get_previous_episode(self):
        """Gibt die vorherige Episode zurück"""
        # Vorherige Episode in dieser Staffel
        prev_ep = Episode.objects.filter(
            season=self.season,
            episode_number__lt=self.episode_number,
            is_active=True
        ).order_by('-episode_number').first()
        
        if prev_ep:
            return prev_ep
        
        # Letzte Episode der vorherigen Staffel
        prev_season = Season.objects.filter(
            series=self.season.series,
            season_number__lt=self.season.season_number,
            is_active=True
        ).order_by('-season_number').first()
        
        if prev_season:
            return Episode.objects.filter(
                season=prev_season,
                is_active=True
            ).order_by('-episode_number').first()
        
        return None


class Quelle(models.Model):
    """Quellenangabe für die öffentliche Seite /quellen/ (im Admin pflegbar)."""
    KATEGORIEN = [
        ('nachrichten', 'Nachrichten'),
        ('video', 'Videos & Sendungen'),
        ('bilder', 'Bilder & Grafiken'),
        ('musik', 'Musik & Audio'),
        ('daten', 'Daten & Wetter'),
        ('technik', 'Technik & Software'),
        ('sonstiges', 'Sonstiges'),
    ]

    name = models.CharField(max_length=200, verbose_name="Name")
    kategorie = models.CharField(max_length=20, choices=KATEGORIEN, default='sonstiges')
    url = models.URLField(max_length=500, blank=True, verbose_name="Link")
    beschreibung = models.TextField(blank=True, help_text="Wofür wird die Quelle genutzt?")
    lizenz = models.CharField(max_length=200, blank=True, help_text="z. B. CC BY 4.0 – leer lassen, wenn nicht nötig")
    reihenfolge = models.PositiveIntegerField(default=0, help_text="Kleinere Zahl = weiter oben")
    is_active = models.BooleanField(default=True, verbose_name="Anzeigen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Quelle"
        verbose_name_plural = "Quellen"
        ordering = ['kategorie', 'reihenfolge', 'name']

    def __str__(self):
        return self.name
