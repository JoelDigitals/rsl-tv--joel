from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
import uuid


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name


class Video(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    source_type = models.CharField(max_length=20, default='youtube')
    source_url = models.URLField(max_length=500)
    
    thumbnail = models.URLField(blank=True)
    duration = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    available_until = models.DateTimeField(null=True, blank=True, 
                                          verbose_name="Verfügbar bis",
                                          help_text="Nach diesem Datum wird das Video automatisch deaktiviert")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def extract_youtube_id(self):
        if not self.source_url:
            return None
        if 'watch?v=' in self.source_url:
            return self.source_url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in self.source_url:
            return self.source_url.split('youtu.be/')[1].split('?')[0]
        return None
    
    def get_thumbnail(self):
        if self.thumbnail:
            return self.thumbnail
        vid = self.extract_youtube_id()
        if vid:
            return f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
        return 'https://placehold.co/640x360/0a6eb4/ffffff?text=VIDEO'
    
    def duration_display(self):
        if not self.duration:
            return "0:00"
        m, s = divmod(self.duration, 60)
        return f"{m}:{s:02d}"
    
    def is_available(self):
        """Prüft ob Video noch verfügbar ist"""
        if not self.is_active:
            return False
        if self.available_until:
            return timezone.now() <= self.available_until
        return True


class Series(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    poster = models.URLField(blank=True)
    year = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    available_until = models.DateTimeField(null=True, blank=True,
                                          verbose_name="Verfügbar bis",
                                          help_text="Nach diesem Datum wird die Serie automatisch deaktiviert")
    
    class Meta:
        verbose_name_plural = "Series"
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_poster(self):
        return self.poster or 'https://placehold.co/400x600/0a6eb4/ffffff?text=SERIE'
    
    def is_available(self):
        """Prüft ob Serie noch verfügbar ist"""
        if not self.is_active:
            return False
        if self.available_until:
            return timezone.now() <= self.available_until
        return True


class Season(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='seasons')
    season_number = models.IntegerField()
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['series', 'season_number']
    
    def __str__(self):
        return f"{self.series.title} - S{self.season_number}"


class Episode(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='episodes')
    episode_number = models.IntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    source_url = models.URLField(max_length=500, blank=True)
    thumbnail = models.URLField(blank=True)
    duration = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['season', 'episode_number']
    
    def __str__(self):
        return f"{self.season.series.title} S{self.season.season_number}E{self.episode_number}"
    
    def get_thumbnail(self):
        return self.thumbnail or 'https://placehold.co/640x360/0a6eb4/ffffff?text=EPISODE'


class LiveStream(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    source_type = models.CharField(max_length=20, default='youtube')
    stream_url = models.URLField(max_length=500)
    
    thumbnail = models.URLField(blank=True)
    
    is_live = models.BooleanField(default=False)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True,
                                        verbose_name="Geplantes Ende",
                                        help_text="Wann endet der Stream (optional)")
    
    is_active = models.BooleanField(default=True)
    available_until = models.DateTimeField(null=True, blank=True,
                                          verbose_name="Verfügbar bis",
                                          help_text="Aufzeichnung verfügbar bis")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_thumbnail(self):
        return self.thumbnail or 'https://placehold.co/640x360/e63946/ffffff?text=LIVE'
    
    def get_current_viewers(self):
        """Holt aktuelle Zuschauerzahl"""
        cutoff = timezone.now() - timedelta(seconds=30)
        return ViewerSession.objects.filter(
            stream=self,
            last_heartbeat__gte=cutoff
        ).count()


class Playlist(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # YouTube Import
    youtube_playlist_url = models.URLField(blank=True, 
                                          verbose_name="YouTube Playlist URL",
                                          help_text="z.B. https://www.youtube.com/playlist?list=PLxxxxx")
    last_import = models.DateTimeField(null=True, blank=True,
                                      verbose_name="Letzter Import")
    auto_import = models.BooleanField(default=False,
                                     verbose_name="Automatischer Import",
                                     help_text="Playlist regelmäßig aktualisieren")
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='items')
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['playlist', 'video']


class ViewerSession(models.Model):
    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name='sessions')
    session_id = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_heartbeat = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.stream.title} - {self.session_id[:10]}"
    
    def is_active(self):
        cutoff = timezone.now() - timedelta(seconds=30)
        return self.last_heartbeat >= cutoff


class ChatMessage(models.Model):
    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name='messages')
    username = models.CharField(max_length=100, default='Gast')
    message = models.TextField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_system = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.username}: {self.message[:30]}"


# ============= WERBUNG MODELS =============

class Advertisement(models.Model):
    """Werbekunde / Werbebuchung"""
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('active', 'Aktiv'),
        ('paused', 'Pausiert'),
        ('expired', 'Abgelaufen'),
    ]
    
    POSITION_CHOICES = [
        ('pre_roll', 'Pre-Roll (vor Video)'),
        ('mid_roll', 'Mid-Roll (während Video)'),
        ('post_roll', 'Post-Roll (nach Video)'),
        ('banner_top', 'Banner Oben'),
        ('banner_side', 'Banner Seitlich'),
        ('overlay', 'Overlay (über Video)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Kunde
    customer_name = models.CharField(max_length=255, verbose_name="Kundenname")
    company_name = models.CharField(max_length=255, verbose_name="Firma")
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    
    # Werbung
    title = models.CharField(max_length=255, verbose_name="Anzeigentitel")
    description = models.TextField(blank=True)
    
    # Video-Werbung
    video_url = models.URLField(max_length=500, blank=True, 
                               help_text="YouTube-Link oder Direct-URL")
    video_duration = models.IntegerField(default=30, help_text="Sekunden")
    
    # Banner/Display-Werbung
    banner_image = models.ImageField(upload_to='ads/banners/', blank=True, null=True)
    banner_link = models.URLField(max_length=500, blank=True)
    banner_width = models.IntegerField(default=728, help_text="Pixel")
    banner_height = models.IntegerField(default=90, help_text="Pixel")
    
    # Position & Targeting
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, 
                               default='pre_roll')
    target_categories = models.ManyToManyField(Category, blank=True,
                                              help_text="Nur in diesen Kategorien zeigen")
    
    # Laufzeit
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    # Status & Budget
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                             default='pending')
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_per_view = models.DecimalField(max_digits=6, decimal_places=2, default=0.05)
    
    # Statistik
    impressions = models.IntegerField(default=0, verbose_name="Einblendungen")
    clicks = models.IntegerField(default=0, verbose_name="Klicks")
    
    # System
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Werbeanzeige"
        verbose_name_plural = "Werbeanzeigen"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.company_name})"
    
    def is_valid(self):
        """Prüft ob Werbung gerade aktiv sein soll"""
        now = timezone.now()
        return (
            self.status == 'active' and
            self.is_active and
            self.start_date <= now <= self.end_date
        )
    
    def ctr(self):
        """Click-Through-Rate in %"""
        if self.impressions == 0:
            return 0
        return round((self.clicks / self.impressions) * 100, 2)
    
    def increment_impression(self):
        """Erhöht Impressions-Counter"""
        self.impressions += 1
        self.save(update_fields=['impressions'])
    
    def increment_click(self):
        """Erhöht Clicks-Counter"""
        self.clicks += 1
        self.save(update_fields=['clicks'])
    
    def extract_youtube_id(self):
        """Extrahiert YouTube Video-ID aus URL"""
        if not self.video_url:
            return None
        if 'watch?v=' in self.video_url:
            return self.video_url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in self.video_url:
            return self.video_url.split('youtu.be/')[1].split('?')[0]
        return None


class AdBreak(models.Model):
    """Werbeunterbrechung während Video/Episode"""
    video = models.ForeignKey(Video, on_delete=models.CASCADE, 
                             null=True, blank=True, related_name='ad_breaks')
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE,
                               null=True, blank=True, related_name='ad_breaks')
    
    # Zeitpunkt
    time_offset = models.IntegerField(help_text="Sekunden nach Start")
    
    # Werbung
    advertisements = models.ManyToManyField(Advertisement, 
                                          through='AdBreakItem')
    
    max_duration = models.IntegerField(default=90, help_text="Max. Dauer in Sekunden")
    is_skippable = models.BooleanField(default=True, 
                                      verbose_name="Überspringbar nach 5 Sek.")
    
    # System
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Werbeunterbrechung"
        verbose_name_plural = "Werbeunterbrechungen"
    
    def __str__(self):
        target = self.video or self.episode
        return f"Werbung nach {self.time_offset}s in {target}"


class AdBreakItem(models.Model):
    """Einzelne Werbung in einer Werbeunterbrechung"""
    ad_break = models.ForeignKey(AdBreak, on_delete=models.CASCADE)
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        unique_together = ['ad_break', 'advertisement']