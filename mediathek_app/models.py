"""
RSL Mediathek - Models
Unterstützt: Serien, Videos, Live-Streams, Playlists
Video-Quellen: YouTube, Google Drive, Dropbox, JDS Cloud Upload
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


# ══════════════════════════════════════════════════════════════════════════════
# KATEGORIEN & TAGS
# ══════════════════════════════════════════════════════════════════════════════

class Category(models.Model):
    """Kategorien für Videos, Serien und Streams"""
    name = models.CharField(max_length=100, verbose_name="Name")
    slug = models.SlugField(unique=True)
    color = models.CharField(max_length=7, default='#0a6eb4', 
                            help_text="Hex-Farbe für UI")
    icon = models.CharField(max_length=50, blank=True,
                           help_text="Bootstrap Icon Name (z.B. 'film', 'camera-video')")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


# ══════════════════════════════════════════════════════════════════════════════
# VIDEOS (Einzelvideos & Episode-Content)
# ══════════════════════════════════════════════════════════════════════════════

class Video(models.Model):
    """Einzelne Videos - können eigenständig oder als Episode verwendet werden"""
    
    SOURCE_CHOICES = [
        ('youtube', 'YouTube'),
        ('gdrive', 'Google Drive'),
        ('dropbox', 'Dropbox'),
        ('direct', 'Direkt-URL'),
        ('jds_cloud', 'JDS Cloud Upload'),
    ]
    
    # Basis-Info
    title = models.CharField(max_length=255, verbose_name="Titel")
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, 
                                 null=True, blank=True, related_name='videos')
    
    # Video-Quelle
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, 
                                   default='youtube')
    source_url = models.URLField(max_length=500, blank=True,
                                help_text="YouTube-Link, Drive-Link, etc.")
    
    # JDS Cloud Upload-Daten
    jds_file_id = models.CharField(max_length=255, blank=True)
    jds_view_url = models.URLField(max_length=1000, blank=True)
    jds_download_url = models.URLField(max_length=1000, blank=True)
    jds_filename = models.CharField(max_length=500, blank=True)
    jds_filesize = models.BigIntegerField(default=0, help_text="Bytes")
    jds_mime_type = models.CharField(max_length=100, blank=True)
    
    # Metadaten
    thumbnail = models.URLField(blank=True, verbose_name="Thumbnail-URL")
    thumbnail_upload = models.ImageField(upload_to='thumbnails/', blank=True,
                                        verbose_name="Thumbnail hochladen")
    duration = models.IntegerField(default=0, help_text="Sekunden")
    views = models.IntegerField(default=0)
    
    # Tags & Zusatz
    tags = models.CharField(max_length=500, blank=True,
                           help_text="Komma-getrennt: Sport, News, Tech")
    featured = models.BooleanField(default=False, verbose_name="Hervorgehoben")
    
    # Status & Zeitstempel
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                   null=True, blank=True)
    
    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Videos"
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['source_type']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Stelle sicher, dass Slug unique ist
            base_slug = self.slug
            counter = 1
            while Video.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_thumbnail(self):
        """Gibt die beste verfügbare Thumbnail-URL zurück"""
        if self.thumbnail_upload:
            return self.thumbnail_upload.url
        if self.thumbnail:
            return self.thumbnail
        # Auto-Thumbnail für YouTube
        if self.source_type == 'youtube' and self.source_url:
            video_id = self.extract_youtube_id()
            if video_id:
                return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        # Fallback
        return '/static/mediathek/img/default-thumbnail.jpg'
    
    def get_stream_url(self):
        """Gibt die korrekte Stream-URL basierend auf source_type zurück"""
        if self.source_type == 'jds_cloud' and self.jds_download_url:
            return self.jds_download_url
        elif self.source_type == 'gdrive' and 'drive.google.com/file/d/' in self.source_url:
            file_id = self.source_url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        elif self.source_type == 'dropbox' and self.source_url:
            return self.source_url.replace('?dl=0', '?dl=1')
        return self.source_url
    
    def extract_youtube_id(self):
        """Extrahiert YouTube Video-ID"""
        if not self.source_url:
            return None
        if 'watch?v=' in self.source_url:
            return self.source_url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in self.source_url:
            return self.source_url.split('youtu.be/')[1].split('?')[0]
        return None
    
    def duration_display(self):
        """Formatierte Dauer: HH:MM:SS oder MM:SS"""
        if not self.duration:
            return "0:00"
        h, remainder = divmod(self.duration, 3600)
        m, s = divmod(remainder, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    
    def increment_views(self):
        """Erhöht View-Counter"""
        self.views += 1
        self.save(update_fields=['views'])


# ══════════════════════════════════════════════════════════════════════════════
# SERIEN-SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class Series(models.Model):
    """TV-Serien"""
    title = models.CharField(max_length=255, verbose_name="Serientitel")
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    
    # Visuals
    poster = models.URLField(blank=True, help_text="Hochformat-Poster")
    poster_upload = models.ImageField(upload_to='series/posters/', blank=True)
    banner = models.URLField(blank=True, help_text="Querformat-Banner")
    banner_upload = models.ImageField(upload_to='series/banners/', blank=True)
    
    # Metadaten
    category = models.ForeignKey(Category, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='series')
    year = models.IntegerField(null=True, blank=True, verbose_name="Jahr")
    rating = models.DecimalField(max_digits=3, decimal_places=1, 
                                 null=True, blank=True,
                                 validators=[MinValueValidator(0), MaxValueValidator(10)])
    tags = models.CharField(max_length=500, blank=True)
    featured = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Serie"
        verbose_name_plural = "Serien"
        ordering = ['title']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            base_slug = self.slug
            counter = 1
            while Series.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_poster(self):
        if self.poster_upload:
            return self.poster_upload.url
        if self.poster:
            return self.poster
        return '/static/mediathek/img/default-poster.jpg'
    
    def get_banner(self):
        if self.banner_upload:
            return self.banner_upload.url
        if self.banner:
            return self.banner
        return '/static/mediathek/img/default-banner.jpg'
    
    def seasons_count(self):
        return self.seasons.filter(is_active=True).count()
    
    def episodes_count(self):
        return Episode.objects.filter(
            season__series=self,
            season__is_active=True,
            is_active=True
        ).count()
    
    def latest_episode(self):
        return Episode.objects.filter(
            season__series=self,
            season__is_active=True,
            is_active=True
        ).order_by('-season__season_number', '-episode_number').first()


class Season(models.Model):
    """Staffeln einer Serie"""
    series = models.ForeignKey(Series, on_delete=models.CASCADE, 
                              related_name='seasons')
    season_number = models.IntegerField(verbose_name="Staffel-Nummer")
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    poster = models.URLField(blank=True)
    poster_upload = models.ImageField(upload_to='series/seasons/', blank=True)
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
            return f"{self.series.title} - S{self.season_number}: {self.title}"
        return f"{self.series.title} - Staffel {self.season_number}"
    
    def episodes_count(self):
        return self.episodes.filter(is_active=True).count()


class Episode(models.Model):
    """Episoden einer Staffel"""
    season = models.ForeignKey(Season, on_delete=models.CASCADE,
                              related_name='episodes')
    episode_number = models.IntegerField(verbose_name="Episoden-Nummer")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Video-Content (kann Video-Objekt verwenden oder eigene Quelle)
    video = models.ForeignKey(Video, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='episodes')
    
    # Alternative: Eigene Video-Quelle
    source_type = models.CharField(max_length=20, choices=Video.SOURCE_CHOICES, 
                                   blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    jds_file_id = models.CharField(max_length=255, blank=True)
    jds_download_url = models.URLField(max_length=1000, blank=True)
    
    # Metadaten
    thumbnail = models.URLField(blank=True)
    thumbnail_upload = models.ImageField(upload_to='series/episodes/', blank=True)
    duration = models.IntegerField(default=0, help_text="Sekunden")
    air_date = models.DateField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Episode"
        verbose_name_plural = "Episoden"
        ordering = ['season', 'episode_number']
        unique_together = ['season', 'episode_number']
    
    def __str__(self):
        return f"{self.season.series.title} S{self.season.season_number:02d}E{self.episode_number:02d} - {self.title}"
    
    def get_thumbnail(self):
        if self.thumbnail_upload:
            return self.thumbnail_upload.url
        if self.thumbnail:
            return self.thumbnail
        if self.video:
            return self.video.get_thumbnail()
        return '/static/mediathek/img/default-thumbnail.jpg'
    
    def get_stream_url(self):
        if self.video:
            return self.video.get_stream_url()
        if self.source_type == 'jds_cloud' and self.jds_download_url:
            return self.jds_download_url
        # Weitere Source-Types wie bei Video
        return self.source_url
    
    def duration_display(self):
        if not self.duration:
            return "0:00"
        h, remainder = divmod(self.duration, 3600)
        m, s = divmod(remainder, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    
    def next_episode(self):
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
            return next_season.episodes.filter(is_active=True).order_by('episode_number').first()
        
        return None
    
    def previous_episode(self):
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
            return prev_season.episodes.filter(is_active=True).order_by('-episode_number').first()
        
        return None


# ══════════════════════════════════════════════════════════════════════════════
# LIVE-STREAMS & PROGRAMM
# ══════════════════════════════════════════════════════════════════════════════

class LiveStream(models.Model):
    """Live-Streams und geplante Live-Sendungen"""
    
    SOURCE_CHOICES = [
        ('youtube', 'YouTube Live'),
        ('twitch', 'Twitch'),
        ('rtmp', 'RTMP (OBS)'),
        ('hls', 'HLS Stream'),
        ('iframe', 'iFrame Embed'),
    ]
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='streams')
    
    # Stream-Quelle
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES,
                                   default='youtube')
    stream_url = models.URLField(max_length=500)
    embed_url = models.URLField(max_length=500, blank=True,
                               help_text="Optionale custom Embed-URL")
    
    # Visuals
    thumbnail = models.URLField(blank=True)
    thumbnail_upload = models.ImageField(upload_to='streams/', blank=True)
    
    # Status
    is_live = models.BooleanField(default=False, verbose_name="Jetzt Live")
    is_featured = models.BooleanField(default=False)
    
    # Zeitplanung
    scheduled_start = models.DateTimeField(null=True, blank=True,
                                          verbose_name="Geplanter Start")
    scheduled_end = models.DateTimeField(null=True, blank=True)
    
    # Zusatz
    location = models.CharField(max_length=255, blank=True)
    viewers = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Live-Stream"
        verbose_name_plural = "Live-Streams"
        ordering = ['-is_live', 'scheduled_start']
    
    def __str__(self):
        prefix = "🔴 LIVE" if self.is_live else "📅"
        return f"{prefix} {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            base_slug = self.slug
            counter = 1
            while LiveStream.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_thumbnail(self):
        if self.thumbnail_upload:
            return self.thumbnail_upload.url
        if self.thumbnail:
            return self.thumbnail
        return '/static/mediathek/img/default-live.jpg'
    
    def get_embed_url(self):
        if self.embed_url:
            return self.embed_url
        
        if self.source_type == 'youtube':
            if 'watch?v=' in self.stream_url:
                vid = self.stream_url.split('watch?v=')[1].split('&')[0]
                return f"https://www.youtube.com/embed/{vid}?autoplay=1"
            elif 'youtu.be/' in self.stream_url:
                vid = self.stream_url.split('youtu.be/')[1].split('?')[0]
                return f"https://www.youtube.com/embed/{vid}?autoplay=1"
        
        elif self.source_type == 'twitch':
            channel = self.stream_url.split('twitch.tv/')[-1].strip('/')
            return f"https://player.twitch.tv/?channel={channel}&parent=localhost&autoplay=true"
        
        return self.stream_url


# ══════════════════════════════════════════════════════════════════════════════
# PLAYLISTS
# ══════════════════════════════════════════════════════════════════════════════

class Playlist(models.Model):
    """Video-Playlists"""
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    
    thumbnail = models.URLField(blank=True)
    thumbnail_upload = models.ImageField(upload_to='playlists/', blank=True)
    
    # Playlist-Verhalten
    PLAY_MODE_CHOICES = [
        ('sequential', 'Sequenziell'),
        ('random', 'Zufällig'),
        ('loop', 'Wiederholen'),
    ]
    play_mode = models.CharField(max_length=20, choices=PLAY_MODE_CHOICES,
                                 default='sequential')
    
    is_public = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            base_slug = self.slug
            counter = 1
            while Playlist.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def videos_count(self):
        return self.items.count()
    
    def total_duration(self):
        return sum(item.video.duration for item in self.items.all() if item.video.duration)


class PlaylistItem(models.Model):
    """Videos in einer Playlist"""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE,
                                related_name='items')
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'added_at']
        unique_together = ['playlist', 'video']
    
    def __str__(self):
        return f"{self.playlist.title} - {self.video.title}"
