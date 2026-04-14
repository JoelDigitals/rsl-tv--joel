"""
RSL Mediathek - Admin Interface
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import (
    Category, Video, Series, Season, Episode,
    LiveStream, Playlist, PlaylistItem
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'color_preview', 'icon', 'videos_count', 
                    'series_count', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Design', {
            'fields': ('color', 'icon', 'order')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width:40px;height:20px;background:{};border-radius:3px;"></div>',
            obj.color
        )
    color_preview.short_description = 'Farbe'
    
    def videos_count(self, obj):
        count = obj.videos.filter(is_active=True).count()
        return format_html('<span style="color:#0a6eb4;font-weight:600;">{}</span>', count)
    videos_count.short_description = 'Videos'
    
    def series_count(self, obj):
        count = obj.series.filter(is_active=True).count()
        return format_html('<span style="color:#0a6eb4;font-weight:600;">{}</span>', count)
    series_count.short_description = 'Serien'


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['thumbnail_preview', 'title', 'source_badge', 'category', 
                    'duration_display', 'views', 'featured', 'is_active', 'published_at']
    list_filter = ['is_active', 'featured', 'source_type', 'category', 'published_at']
    list_editable = ['featured', 'is_active']
    search_fields = ['title', 'description', 'tags']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    readonly_fields = ['views', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('title', 'slug', 'description', 'category', 'tags')
        }),
        ('Video-Quelle', {
            'fields': ('source_type', 'source_url')
        }),
        ('JDS Cloud Upload (automatisch)', {
            'fields': ('jds_file_id', 'jds_view_url', 'jds_download_url', 
                      'jds_filename', 'jds_filesize', 'jds_mime_type'),
            'classes': ('collapse',)
        }),
        ('Thumbnail', {
            'fields': ('thumbnail', 'thumbnail_upload')
        }),
        ('Metadaten', {
            'fields': ('duration', 'views', 'featured')
        }),
        ('Status & Zeitstempel', {
            'fields': ('is_active', 'published_at', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def thumbnail_preview(self, obj):
        thumb = obj.get_thumbnail()
        return format_html(
            '<img src="{}" style="width:80px;height:45px;object-fit:cover;border-radius:4px;">',
            thumb
        )
    thumbnail_preview.short_description = 'Thumb'
    
    def source_badge(self, obj):
        colors = {
            'youtube': '#FF0000',
            'gdrive': '#4285F4',
            'dropbox': '#0061FF',
            'jds_cloud': '#0a6eb4',
            'direct': '#666'
        }
        labels = {
            'youtube': 'YT',
            'gdrive': 'Drive',
            'dropbox': 'Drop',
            'jds_cloud': 'JDS',
            'direct': 'URL'
        }
        color = colors.get(obj.source_type, '#666')
        label = labels.get(obj.source_type, obj.source_type.upper())
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:3px;font-size:0.7rem;font-weight:700;">{}</span>',
            color, label
        )
    source_badge.short_description = 'Quelle'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class SeasonInline(admin.TabularInline):
    model = Season
    extra = 0
    fields = ['season_number', 'title', 'year', 'is_active']
    show_change_link = True


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ['poster_preview', 'title', 'category', 'year', 'rating_stars',
                    'seasons_info', 'episodes_info', 'featured', 'is_active']
    list_filter = ['is_active', 'featured', 'category', 'year']
    list_editable = ['featured', 'is_active']
    search_fields = ['title', 'description', 'tags']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SeasonInline]
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('title', 'slug', 'description', 'category', 'tags')
        }),
        ('Visuals', {
            'fields': (('poster', 'poster_upload'), ('banner', 'banner_upload'))
        }),
        ('Metadaten', {
            'fields': ('year', 'rating', 'featured')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def poster_preview(self, obj):
        poster = obj.get_poster()
        return format_html(
            '<img src="{}" style="width:50px;height:75px;object-fit:cover;border-radius:4px;">',
            poster
        )
    poster_preview.short_description = 'Poster'
    
    def rating_stars(self, obj):
        if not obj.rating:
            return '-'
        stars = '⭐' * int(obj.rating)
        return format_html(
            '<span style="color:#FFD700;">{}</span> <span style="color:#0a6eb4;font-weight:600;">{}</span>',
            stars[:5], obj.rating
        )
    rating_stars.short_description = 'Rating'
    
    def seasons_info(self, obj):
        count = obj.seasons_count()
        return format_html(
            '<span style="background:#0d1a27;color:#5baed4;padding:3px 10px;border-radius:10px;font-weight:700;">{} Staffel{}</span>',
            count, 'n' if count != 1 else ''
        )
    seasons_info.short_description = 'Staffeln'
    
    def episodes_info(self, obj):
        count = obj.episodes_count()
        return format_html(
            '<span style="background:#0d1a27;color:#5baed4;padding:3px 10px;border-radius:10px;font-weight:700;">{} Ep.</span>',
            count
        )
    episodes_info.short_description = 'Episoden'


class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    fields = ['episode_number', 'title', 'duration', 'air_date', 'is_active']
    readonly_fields = ['duration']
    show_change_link = True


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['season_code', 'series', 'title', 'year', 'episodes_info', 'is_active']
    list_filter = ['is_active', 'series', 'year']
    list_editable = ['is_active']
    search_fields = ['title', 'description', 'series__title']
    autocomplete_fields = ['series']
    inlines = [EpisodeInline]
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('series', 'season_number')
        }),
        ('Details', {
            'fields': ('title', 'description', 'year')
        }),
        ('Visual', {
            'fields': (('poster', 'poster_upload'),)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    
    def season_code(self, obj):
        return format_html(
            '<code style="background:#0d1a27;color:#00c4ff;padding:4px 10px;border-radius:4px;font-weight:700;">S{:02d}</code>',
            obj.season_number
        )
    season_code.short_description = 'Code'
    
    def episodes_info(self, obj):
        count = obj.episodes_count()
        return format_html(
            '<span style="color:#0a6eb4;font-weight:600;">{} Episode{}</span>',
            count, 'n' if count != 1 else ''
        )
    episodes_info.short_description = 'Episoden'


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ['thumbnail_preview', 'episode_code', 'title', 'season',
                    'duration_display', 'air_date', 'video_source', 'is_active']
    list_filter = ['is_active', 'season__series', 'season', 'air_date', 'source_type']
    list_editable = ['is_active']
    search_fields = ['title', 'description', 'season__series__title']
    autocomplete_fields = ['season', 'video']
    date_hierarchy = 'air_date'
    
    fieldsets = (
        ('Episode-Info', {
            'fields': ('season', 'episode_number', 'title', 'description')
        }),
        ('Video (Option 1: Verknüpfung)', {
            'fields': ('video',),
            'description': 'Wähle ein bestehendes Video aus der Mediathek'
        }),
        ('Video (Option 2: Eigene Quelle)', {
            'fields': ('source_type', 'source_url', 'jds_file_id', 'jds_download_url')
        }),
        ('Thumbnail', {
            'fields': (('thumbnail', 'thumbnail_upload'),)
        }),
        ('Metadaten', {
            'fields': ('duration', 'air_date')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'duration']
    
    def thumbnail_preview(self, obj):
        thumb = obj.get_thumbnail()
        return format_html(
            '<img src="{}" style="width:80px;height:45px;object-fit:cover;border-radius:4px;">',
            thumb
        )
    thumbnail_preview.short_description = 'Thumb'
    
    def episode_code(self, obj):
        return format_html(
            '<code style="background:#0d1a27;color:#00c4ff;padding:4px 10px;border-radius:4px;font-weight:700;">S{:02d}E{:02d}</code>',
            obj.season.season_number,
            obj.episode_number
        )
    episode_code.short_description = 'Code'
    
    def video_source(self, obj):
        if obj.video:
            return format_html(
                '<span style="background:#073e6e;color:#fff;padding:3px 8px;border-radius:3px;font-size:0.7rem;">📹 Verknüpft</span>'
            )
        elif obj.source_type:
            colors = {
                'youtube': '#FF0000',
                'gdrive': '#4285F4',
                'jds_cloud': '#0a6eb4',
            }
            color = colors.get(obj.source_type, '#666')
            return format_html(
                '<span style="background:{};color:#fff;padding:3px 8px;border-radius:3px;font-size:0.7rem;">{}</span>',
                color, obj.get_source_type_display()
            )
        return '-'
    video_source.short_description = 'Quelle'


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ['thumbnail_preview', 'title', 'status_badge', 'source_badge',
                    'category', 'scheduled_start', 'viewers', 'is_featured', 'is_active']
    list_filter = ['is_live', 'is_featured', 'is_active', 'source_type', 'category']
    list_editable = ['is_featured', 'is_active']
    search_fields = ['title', 'description', 'location']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'scheduled_start'
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('title', 'slug', 'description', 'category')
        }),
        ('Stream-Quelle', {
            'fields': ('source_type', 'stream_url', 'embed_url')
        }),
        ('Thumbnail', {
            'fields': (('thumbnail', 'thumbnail_upload'),)
        }),
        ('Status', {
            'fields': ('is_live', 'is_featured', 'viewers')
        }),
        ('Zeitplanung', {
            'fields': ('scheduled_start', 'scheduled_end', 'location')
        }),
        ('System', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def thumbnail_preview(self, obj):
        thumb = obj.get_thumbnail()
        return format_html(
            '<img src="{}" style="width:80px;height:45px;object-fit:cover;border-radius:4px;">',
            thumb
        )
    thumbnail_preview.short_description = 'Thumb'
    
    def status_badge(self, obj):
        if obj.is_live:
            return format_html(
                '<span style="background:#e63946;color:#fff;padding:4px 10px;border-radius:10px;font-weight:700;animation:pulse 2s infinite;">🔴 LIVE</span>'
            )
        return format_html(
            '<span style="background:#666;color:#fff;padding:4px 10px;border-radius:10px;">Offline</span>'
        )
    status_badge.short_description = 'Status'
    
    def source_badge(self, obj):
        colors = {
            'youtube': '#FF0000',
            'twitch': '#9146FF',
            'rtmp': '#0a6eb4',
            'hls': '#00c4ff',
            'iframe': '#666'
        }
        color = colors.get(obj.source_type, '#666')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:3px;font-size:0.7rem;font-weight:700;">{}</span>',
            color, obj.get_source_type_display()
        )
    source_badge.short_description = 'Quelle'


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 1
    autocomplete_fields = ['video']
    fields = ['video', 'order']


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ['title', 'videos_info', 'play_mode', 'is_public', 
                    'is_active', 'created_by', 'created_at']
    list_filter = ['is_public', 'is_active', 'play_mode', 'created_at']
    list_editable = ['is_public', 'is_active']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PlaylistItemInline]
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('title', 'slug', 'description')
        }),
        ('Thumbnail', {
            'fields': (('thumbnail', 'thumbnail_upload'),)
        }),
        ('Einstellungen', {
            'fields': ('play_mode', 'is_public', 'is_active')
        }),
        ('System', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def videos_info(self, obj):
        count = obj.videos_count()
        duration = obj.total_duration()
        h, remainder = divmod(duration, 3600)
        m, s = divmod(remainder, 60)
        time_str = f"{h}h {m}min" if h > 0 else f"{m}min"
        return format_html(
            '<span style="color:#0a6eb4;font-weight:600;">{} Videos</span> · <span style="color:#666;">{}</span>',
            count, time_str
        )
    videos_info.short_description = 'Inhalt'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Admin-Site Anpassungen
admin.site.site_header = "RSL Mediathek Administration"
admin.site.site_title = "RSL Mediathek"
admin.site.index_title = "Mediathek Management"
