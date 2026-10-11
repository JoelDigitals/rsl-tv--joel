"""
Werbungs-Models für RSL Mediathek
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


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
    banner_image = models.ImageField(upload_to='ads/banners/', blank=True)
    banner_link = models.URLField(max_length=500, blank=True)
    banner_width = models.IntegerField(default=728, help_text="Pixel")
    banner_height = models.IntegerField(default=90, help_text="Pixel")
    
    # Position & Targeting
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, 
                               default='pre_roll')
    target_categories = models.ManyToManyField('Category', blank=True,
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


class AdBreak(models.Model):
    """Werbeunterbrechung während Video/Episode"""
    video = models.ForeignKey('Video', on_delete=models.CASCADE, 
                             null=True, blank=True, related_name='ad_breaks')
    episode = models.ForeignKey('Episode', on_delete=models.CASCADE,
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
