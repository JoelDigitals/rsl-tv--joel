"""
RSL TV – Models (vollständig überarbeitet)
Joel Digitals
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import os


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
        # Format: [logo][main] overlay
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
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='youtube')
    source_url = models.URLField(max_length=500)
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
        if self.source_type == 'gdrive' and 'drive.google.com/file/d/' in self.source_url:
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
    # Verknüpfung zu einer gebuchten Werbung (optional – für eigene Sender-Trailer leer)
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

        # 2. Aktive Werbespots (gebuchte + freigeschaltete)
        from django.utils import timezone
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
        ).order_by('?'))  # Zufällige Reihenfolge

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


class Camera(models.Model):
    """Kamera für Live-Regie"""
    name = models.CharField(max_length=100, help_text="z.B. 'Kamera 1', 'Overhead'")
    stream_url = models.URLField(max_length=500, help_text="RTMP/RTSP/HTTP Stream URL")
    is_active = models.BooleanField(default=True)
    preview_url = models.URLField(max_length=500, blank=True, help_text="Optional: Vorschau-URL")
    order = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Kamera"
        verbose_name_plural = "Kameras"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class LiveDirector(models.Model):
    """Aktuell ausgewählte Kamera für Live-Sendung"""
    live_stream = models.OneToOneField('LiveStream', on_delete=models.CASCADE, related_name='director')
    selected_camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Live-Regie"

    def __str__(self):
        return f"Regie für {self.live_stream.title}"


class DirectorRoom(models.Model):
    """Regieraum mit eigenen Kameras und Kontrollen"""
    name = models.CharField(max_length=100, help_text="z.B. 'Studio A', 'Studio B', 'Sport-Regie'")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Streaming-Konfiguration für diesen Regieraum
    youtube_stream_key = models.CharField(max_length=200, blank=True, help_text="YouTube Stream Key für diesen Raum")
    twitch_stream_key = models.CharField(max_length=200, blank=True, help_text="Twitch Stream Key für diesen Raum")
    
    # Aktueller Status
    is_streaming = models.BooleanField(default=False)
    current_output = models.TextField(blank=True, help_text="Aktuelle Stream-URL oder Status")
    
    class Meta:
        verbose_name = "Regieraum"
        verbose_name_plural = "Regieräume"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class DirectorRoomCamera(models.Model):
    """Zuordnung von Kameras zu Regieräumen"""
    room = models.ForeignKey(DirectorRoom, on_delete=models.CASCADE, related_name='room_cameras')
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Regieraum-Kamera"
        verbose_name_plural = "Regieraum-Kameras"
        ordering = ['room', 'order']
        unique_together = ['room', 'camera']
    
    def __str__(self):
        return f"{self.room.name} - {self.camera.name}"


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