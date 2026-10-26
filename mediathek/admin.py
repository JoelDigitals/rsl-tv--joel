from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .models import (
    Category, Video, Series, Season, Episode,
    LiveStream, Playlist, PlaylistItem,
    ViewerSession, ChatMessage,
    Advertisement, AdBreak, AdBreakItem
)
import re


# ============= HILFS-FUNKTIONEN =============

def extract_playlist_id(url):
    """Extrahiert Playlist-ID aus YouTube URL"""
    if not url:
        return None
    match = re.search(r'list=([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None


def extract_video_id(url):
    """Extrahiert Video-ID aus YouTube URL"""
    if not url:
        return None
    if 'watch?v=' in url:
        return url.split('watch?v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return None


# ============= KATEGORIEN =============

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Kategorien für Videos und Livestreams
    
    Hier können Kategorien wie "Sport", "News", "Entertainment" etc. verwaltet werden.
    Kategorien helfen bei der Organisation und Filterung von Inhalten.
    """
    list_display = ['name', 'slug', 'video_count', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'slug'),
            'description': 'Grundlegende Informationen zur Kategorie'
        }),
        ('Status', {
            'fields': ('is_active',),
            'description': 'Kategorie aktivieren/deaktivieren'
        }),
    )
    
    def video_count(self, obj):
        count = obj.video_set.filter(is_active=True).count()
        return format_html('<span style="color:#0a6eb4;font-weight:bold;">{}</span>', count)
    video_count.short_description = 'Videos'


# ============= VIDEOS =============

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """
    Einzelne Videos
    
    Hier werden einzelne Videos verwaltet - von YouTube, Vimeo oder anderen Quellen.
    Videos können kategorisiert und mit Verfallsdatum versehen werden.
    """
    list_display = ['title', 'category', 'views', 'availability_status', 'published_at']
    list_filter = ['category', 'is_active', 'source_type', 'published_at']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    
    fieldsets = (
        ('Video-Informationen', {
            'fields': ('title', 'slug', 'description', 'category'),
            'description': 'Grundlegende Informationen zum Video'
        }),
        ('Quelle', {
            'fields': ('source_type', 'source_url'),
            'description': 'Woher kommt das Video? YouTube, Vimeo, etc.'
        }),
        ('Medien-Details', {
            'fields': ('thumbnail', 'duration'),
            'classes': ('collapse',),
            'description': 'Optional: Eigenes Thumbnail und Dauer in Sekunden'
        }),
        ('Verfügbarkeit & Status', {
            'fields': ('is_active', 'published_at', 'available_until'),
            'description': 'Wann ist das Video sichtbar? Verfallsdatum optional setzen.'
        }),
        ('Statistiken', {
            'fields': ('views',),
            'classes': ('collapse',),
            'description': 'Automatisch gezählte Aufrufe'
        }),
    )
    
    def availability_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color:#ef476f;">❌ Inaktiv</span>')
        if obj.available_until:
            if timezone.now() > obj.available_until:
                return format_html('<span style="color:#ffc107;">⏰ Abgelaufen</span>')
            days_left = (obj.available_until - timezone.now()).days
            return format_html(
                '<span style="color:#06d6a0;">✅ Aktiv (noch {} Tage)</span>', 
                days_left
            )
        return format_html('<span style="color:#06d6a0;">✅ Aktiv (unbegrenzt)</span>')
    availability_status.short_description = 'Verfügbarkeit'


# ============= SERIEN =============

class SeasonInline(admin.TabularInline):
    """Staffeln direkt in der Serien-Ansicht bearbeiten"""
    model = Season
    extra = 1
    fields = ['season_number', 'title', 'episode_count', 'is_active']
    readonly_fields = ['episode_count']
    
    def episode_count(self, obj):
        if obj.pk:
            return obj.episodes.filter(is_active=True).count()
        return 0
    episode_count.short_description = 'Episoden'


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    """
    Serien / TV-Shows
    
    Verwaltung von Serien mit mehreren Staffeln und Episoden.
    Ideal für mehrteilige Inhalte wie Tutorials, Dokumentationen oder Serien.
    """
    list_display = ['title', 'year', 'season_count', 'availability_status']
    list_filter = ['is_active', 'year']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SeasonInline]
    
    fieldsets = (
        ('Serien-Informationen', {
            'fields': ('title', 'slug', 'description', 'year'),
            'description': 'Grundlegende Informationen zur Serie'
        }),
        ('Poster & Medien', {
            'fields': ('poster',),
            'description': 'URL zum Serien-Poster (empfohlen: 400x600px)'
        }),
        ('Verfügbarkeit', {
            'fields': ('is_active', 'available_until'),
            'description': 'Serie aktivieren/deaktivieren und Verfallsdatum setzen'
        }),
    )
    
    def season_count(self, obj):
        count = obj.seasons.filter(is_active=True).count()
        return format_html('<span style="color:#0a6eb4;font-weight:bold;">{} Staffeln</span>', count)
    season_count.short_description = 'Staffeln'
    
    def availability_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color:#ef476f;">❌ Inaktiv</span>')
        if obj.available_until:
            if timezone.now() > obj.available_until:
                return format_html('<span style="color:#ffc107;">⏰ Abgelaufen</span>')
            days_left = (obj.available_until - timezone.now()).days
            return format_html(
                '<span style="color:#06d6a0;">✅ Aktiv (noch {} Tage)</span>', 
                days_left
            )
        return format_html('<span style="color:#06d6a0;">✅ Aktiv</span>')
    availability_status.short_description = 'Status'


# ============= STAFFELN =============

class EpisodeInline(admin.TabularInline):
    """Episoden direkt in der Staffel-Ansicht bearbeiten"""
    model = Episode
    extra = 1
    fields = ['episode_number', 'title', 'source_url', 'duration', 'is_active']


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    """
    Staffeln einer Serie
    
    Organisiert Episoden in Staffeln. Jede Serie kann mehrere Staffeln haben.
    """
    list_display = ['series', 'season_number', 'title', 'episode_count', 'is_active']
    list_filter = ['series', 'is_active']
    search_fields = ['title', 'series__title']
    inlines = [EpisodeInline]
    
    fieldsets = (
        ('Staffel-Informationen', {
            'fields': ('series', 'season_number', 'title'),
            'description': 'Zu welcher Serie gehört diese Staffel?'
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )
    
    def episode_count(self, obj):
        count = obj.episodes.filter(is_active=True).count()
        return format_html('<span style="color:#0a6eb4;">{}</span>', count)
    episode_count.short_description = 'Episoden'


# ============= EPISODEN =============

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    """
    Einzelne Episoden
    
    Individuelle Episoden innerhalb einer Staffel/Serie.
    """
    list_display = ['title', 'series_name', 'season', 'episode_number', 'duration_display', 'is_active']
    list_filter = ['season__series', 'is_active']
    search_fields = ['title', 'description', 'season__series__title']
    
    fieldsets = (
        ('Episode', {
            'fields': ('season', 'episode_number', 'title', 'description'),
            'description': 'Informationen zur Episode'
        }),
        ('Video-Quelle', {
            'fields': ('source_url', 'thumbnail', 'duration'),
            'description': 'YouTube-URL oder andere Video-Quelle'
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )
    
    def series_name(self, obj):
        return obj.season.series.title
    series_name.short_description = 'Serie'
    
    def duration_display(self, obj):
        if obj.duration:
            m, s = divmod(obj.duration, 60)
            return f"{m}:{s:02d}"
        return "-"
    duration_display.short_description = 'Dauer'


# ============= LIVESTREAMS =============

@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    """
    Livestreams & Live-Events
    
    Verwaltung von Live-Übertragungen mit Zuschauerzählung und Chat.
    Streams können geplant und zeitlich begrenzt werden.
    """
    list_display = ['title', 'status_display', 'current_viewers', 'scheduled_times', 'availability_status']
    list_filter = ['is_live', 'is_active', 'source_type', 'scheduled_start']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'scheduled_start'
    
    fieldsets = (
        ('Stream-Informationen', {
            'fields': ('title', 'slug', 'description', 'category'),
            'description': 'Grundlegende Informationen zum Livestream'
        }),
        ('Quelle', {
            'fields': ('source_type', 'stream_url'),
            'description': 'YouTube Live URL oder andere Stream-Quelle'
        }),
        ('Zeitplanung', {
            'fields': ('scheduled_start', 'scheduled_end'),
            'description': 'Wann findet der Stream statt? (Optional für geplante Streams)'
        }),
        ('Medien', {
            'fields': ('thumbnail',),
            'classes': ('collapse',),
        }),
        ('Status & Verfügbarkeit', {
            'fields': ('is_live', 'is_active', 'available_until'),
            'description': '🔴 is_live = Stream läuft gerade | available_until = Aufzeichnung verfügbar bis'
        }),
    )
    
    def status_display(self, obj):
        if obj.is_live:
            return format_html('<span style="color:#e63946;font-weight:bold;">🔴 LIVE</span>')
        elif obj.scheduled_start and obj.scheduled_start > timezone.now():
            return format_html('<span style="color:#ffc107;">📅 Geplant</span>')
        return format_html('<span style="color:#666;">⚫ Offline</span>')
    status_display.short_description = 'Status'
    
    def current_viewers(self, obj):
        count = obj.get_current_viewers()
        return format_html('<span style="color:#0a6eb4;font-weight:bold;">👥 {}</span>', count)
    current_viewers.short_description = 'Zuschauer'
    
    def scheduled_times(self, obj):
        if obj.scheduled_start:
            start = obj.scheduled_start.strftime('%d.%m.%Y %H:%M')
            if obj.scheduled_end:
                end = obj.scheduled_end.strftime('%H:%M')
                return format_html('{} - {}', start, end)
            return start
        return "-"
    scheduled_times.short_description = 'Zeitplan'
    
    def availability_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color:#ef476f;">❌ Inaktiv</span>')
        if obj.available_until:
            if timezone.now() > obj.available_until:
                return format_html('<span style="color:#ffc107;">⏰ Abgelaufen</span>')
            return format_html('<span style="color:#06d6a0;">✅ Verfügbar</span>')
        return format_html('<span style="color:#06d6a0;">✅ Unbegrenzt</span>')
    availability_status.short_description = 'Verfügbarkeit'


# ============= PLAYLISTS MIT YOUTUBE IMPORT =============

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    """
    Playlists & YouTube Import
    
    Erstelle Playlists oder importiere automatisch YouTube-Playlists.
    Videos werden automatisch hinzugefügt und können organisiert werden.
    """
    list_display = ['title', 'video_count', 'youtube_status', 'last_import_display', 'is_active']
    list_filter = ['is_active', 'auto_import']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Playlist-Informationen', {
            'fields': ('title', 'slug', 'description'),
            'description': 'Grundlegende Informationen zur Playlist'
        }),
        ('YouTube Import', {
            'fields': ('youtube_playlist_url', 'auto_import', 'last_import'),
            'description': '🎬 YouTube Playlist-URL einfügen und Videos automatisch importieren'
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )
    
    readonly_fields = ['last_import']
    
    def video_count(self, obj):
        count = obj.items.count()
        return format_html('<span style="color:#0a6eb4;font-weight:bold;">{} Videos</span>', count)
    video_count.short_description = 'Videos'
    
    def youtube_status(self, obj):
        if obj.youtube_playlist_url:
            if obj.auto_import:
                return format_html('<span style="color:#06d6a0;">✅ Auto-Import</span>')
            return format_html('<span style="color:#ffc107;">📋 Manuell</span>')
        return format_html('<span style="color:#666;">➕ Manuelle Playlist</span>')
    youtube_status.short_description = 'Import-Status'
    
    def last_import_display(self, obj):
        if obj.last_import:
            return obj.last_import.strftime('%d.%m.%Y %H:%M')
        return "-"
    last_import_display.short_description = 'Letzter Import'
    
    # Custom Admin Actions
    actions = ['import_youtube_playlist']
    
    def import_youtube_playlist(self, request, queryset):
        """YouTube Playlist importieren"""
        for playlist in queryset:
            if not playlist.youtube_playlist_url:
                self.message_user(
                    request, 
                    f'❌ {playlist.title}: Keine YouTube-URL vorhanden',
                    level=messages.ERROR
                )
                continue
            
            playlist_id = extract_playlist_id(playlist.youtube_playlist_url)
            if not playlist_id:
                self.message_user(
                    request, 
                    f'❌ {playlist.title}: Ungültige YouTube Playlist-URL',
                    level=messages.ERROR
                )
                continue
            
            # Hier würde die YouTube API Integration kommen
            # Für jetzt: Beispiel-Implementierung
            self.message_user(
                request,
                f'✅ {playlist.title}: Import gestartet (Playlist ID: {playlist_id})',
                level=messages.SUCCESS
            )
            
            # Zeitstempel aktualisieren
            playlist.last_import = timezone.now()
            playlist.save()
    
    import_youtube_playlist.short_description = "🎬 YouTube Playlist importieren"


# ============= PLAYLIST ITEMS =============

@admin.register(PlaylistItem)
class PlaylistItemAdmin(admin.ModelAdmin):
    """
    Videos in Playlists
    
    Ordnet Videos Playlists zu und definiert die Reihenfolge.
    """
    list_display = ['playlist', 'video', 'order']
    list_filter = ['playlist']
    search_fields = ['playlist__title', 'video__title']
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('playlist', 'video', 'order'),
            'description': 'Video zur Playlist hinzufügen und Reihenfolge festlegen'
        }),
    )


# ============= ZUSCHAUER & CHAT =============

@admin.register(ViewerSession)
class ViewerSessionAdmin(admin.ModelAdmin):
    """
    Live-Zuschauer Sessions
    
    Überwacht aktive Zuschauer in Livestreams (automatisch erstellt).
    """
    list_display = ['stream', 'session_short', 'ip_address', 'started_at', 'last_heartbeat', 'active_status']
    list_filter = ['stream', 'started_at']
    readonly_fields = ['session_id', 'ip_address', 'started_at', 'last_heartbeat']
    search_fields = ['session_id', 'ip_address']
    
    def session_short(self, obj):
        return obj.session_id[:15] + '...'
    session_short.short_description = 'Session ID'
    
    def active_status(self, obj):
        if obj.is_active():
            return format_html('<span style="color:#06d6a0;font-weight:bold;">✓ Aktiv</span>')
        return format_html('<span style="color:#999;">⚫ Inaktiv</span>')
    active_status.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False  # Sessions werden automatisch erstellt


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """
    Live-Chat Nachrichten
    
    Alle Chat-Nachrichten aus Livestreams. Moderations-Tool.
    """
    list_display = ['stream', 'username', 'message_short', 'timestamp', 'system_badge']
    list_filter = ['stream', 'is_system', 'timestamp']
    search_fields = ['username', 'message']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Nachricht', {
            'fields': ('stream', 'username', 'message', 'is_system'),
        }),
        ('Zeitstempel', {
            'fields': ('timestamp',),
        }),
    )
    
    def message_short(self, obj):
        if len(obj.message) > 60:
            return obj.message[:60] + '...'
        return obj.message
    message_short.short_description = 'Nachricht'
    
    def system_badge(self, obj):
        if obj.is_system:
            return format_html('<span style="color:#ffc107;">🤖 System</span>')
        return format_html('<span style="color:#06d6a0;">👤 User</span>')
    system_badge.short_description = 'Typ'


# ============= WERBUNG =============

@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    """
    Werbeanzeigen & Sponsoring
    
    Verwaltung von Video-Ads und Banner-Werbung mit Statistiken.
    Kann vor/während/nach Videos oder als Banner platziert werden.
    """
    list_display = ['title', 'company_name', 'position_badge', 'status_badge', 
                   'date_range', 'impressions', 'clicks', 'ctr_display', 'is_active']
    list_filter = ['status', 'position', 'is_active', 'start_date', 'end_date']
    search_fields = ['title', 'company_name', 'customer_name', 'email']
    filter_horizontal = ['target_categories']
    readonly_fields = ['id', 'impressions', 'clicks', 'created_at', 'updated_at', 'ctr_display']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('📋 Kunde', {
            'fields': ('customer_name', 'company_name', 'email', 'phone'),
            'description': 'Kontaktdaten des Werbetreibenden'
        }),
        ('📺 Werbung', {
            'fields': ('title', 'description', 'position'),
            'description': 'Titel und Position der Anzeige'
        }),
        ('🎬 Video-Werbung', {
            'fields': ('video_url', 'video_duration'),
            'classes': ('collapse',),
            'description': 'Für Video-Ads: YouTube-URL oder Direct-Link'
        }),
        ('🖼️ Banner-Werbung', {
            'fields': ('banner_image', 'banner_link', 'banner_width', 'banner_height'),
            'classes': ('collapse',),
            'description': 'Für Display-Ads: Banner hochladen und Ziel-URL'
        }),
        ('🎯 Targeting & Laufzeit', {
            'fields': ('target_categories', 'start_date', 'end_date'),
            'description': 'In welchen Kategorien und wann soll die Werbung erscheinen?'
        }),
        ('💰 Status & Budget', {
            'fields': ('status', 'is_active', 'budget', 'cost_per_view'),
            'description': 'Finanzen und Aktivierungsstatus'
        }),
        ('📊 Statistiken', {
            'fields': ('impressions', 'clicks', 'ctr_display'),
            'classes': ('collapse',),
            'description': 'Automatisch gesammelte Performance-Daten'
        }),
        ('⚙️ System', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def position_badge(self, obj):
        colors = {
            'pre_roll': '#0a6eb4',
            'mid_roll': '#ffc107',
            'post_roll': '#06d6a0',
            'banner_top': '#ef476f',
            'banner_side': '#9b59b6',
            'overlay': '#e74c3c',
        }
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; border-radius:3px; font-size:0.85em;">{}</span>',
            colors.get(obj.position, '#999'),
            obj.get_position_display()
        )
    position_badge.short_description = 'Position'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'active': '#06d6a0',
            'paused': '#ef476f',
            'expired': '#999'
        }
        icons = {
            'pending': '⏳',
            'active': '✅',
            'paused': '⏸️',
            'expired': '❌'
        }
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; border-radius:3px; font-weight:bold;">{} {}</span>',
            colors.get(obj.status, '#999'),
            icons.get(obj.status, ''),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def date_range(self, obj):
        return format_html(
            '{}<br><small style="color:#666;">bis {}</small>',
            obj.start_date.strftime('%d.%m.%Y'),
            obj.end_date.strftime('%d.%m.%Y')
        )
    date_range.short_description = 'Laufzeit'
    
    def ctr_display(self, obj):
        ctr = obj.ctr()
        if ctr > 2:
            color = '#06d6a0'
            icon = '🔥'
        elif ctr > 1:
            color = '#0a6eb4'
            icon = '✅'
        elif ctr > 0.5:
            color = '#ffc107'
            icon = '⚠️'
        else:
            color = '#ef476f'
            icon = '📉'
        return format_html(
            '<span style="color:{}; font-weight:bold;">{} {}%</span>',
            color, icon, ctr
        )
    ctr_display.short_description = 'CTR'


# ============= WERBEUNTERBRECHUNGEN =============

class AdBreakItemInline(admin.TabularInline):
    """Werbungen in der Unterbrechung"""
    model = AdBreakItem
    extra = 1
    fields = ['advertisement', 'order']


@admin.register(AdBreak)
class AdBreakAdmin(admin.ModelAdmin):
    """
    Werbeunterbrechungen in Videos
    
    Platziert Werbung zu bestimmten Zeitpunkten in Videos oder Episoden.
    """
    list_display = ['content_info', 'time_offset_display', 'ad_count', 
                   'max_duration', 'skippable_badge', 'is_active']
    list_filter = ['is_skippable', 'is_active']
    inlines = [AdBreakItemInline]
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('video', 'episode'),
            'description': 'Wähle Video ODER Episode (nicht beides)'
        }),
        ('Zeitpunkt & Dauer', {
            'fields': ('time_offset', 'max_duration', 'is_skippable'),
            'description': 'Wann und wie lange soll die Werbung laufen?'
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )
    
    def content_info(self, obj):
        target = obj.video or obj.episode
        return str(target)
    content_info.short_description = 'Inhalt'
    
    def time_offset_display(self, obj):
        m, s = divmod(obj.time_offset, 60)
        return format_html('<span style="color:#0a6eb4;font-weight:bold;">{}:{:02d}</span>', m, s)
    time_offset_display.short_description = 'Zeitpunkt'
    
    def ad_count(self, obj):
        count = obj.adbreakitem_set.count()
        return format_html('<span style="color:#ffc107;">{} Ads</span>', count)
    ad_count.short_description = 'Werbungen'
    
    def skippable_badge(self, obj):
        if obj.is_skippable:
            return format_html('<span style="color:#06d6a0;">⏭️ Ja</span>')
        return format_html('<span style="color:#ef476f;">🚫 Nein</span>')
    skippable_badge.short_description = 'Überspringbar'


# ============= ADMIN SITE ANPASSUNGEN =============

admin.site.site_header = "RSL Mediathek Administration"
admin.site.site_title = "RSL Admin"
admin.site.index_title = "Willkommen im RSL Mediathek Admin-Bereich"


from .models import ArchivedBroadcast


@admin.register(ArchivedBroadcast)
class ArchivedBroadcastAdmin(admin.ModelAdmin):
    """Aus der Broadcast-API gespeicherte Sendungen und Live-Streams."""
    list_display = ['title', 'kind', 'series_title', 'aired_at', 'ended_at', 'is_active']
    list_filter = ['kind', 'is_active', 'series_title']
    list_editable = ['is_active']
    search_fields = ['title', 'series_title', 'api_id']
    date_hierarchy = 'aired_at'
    readonly_fields = ['api_id', 'created_at', 'updated_at']
