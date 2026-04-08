"""
RSL TV – Admin Panel (vollständig)
Joel Digitals
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.urls import path
from django.shortcuts import redirect
from .models import (
    Category, SenderLogo, Video, AdVideo, AdBreakTemplate, AdBreak, LiveAdBreak,
    Schedule, LiveStream, Advertisement, AdBooking,
    PlaylistItem, PlaylistEntry, NewsItem, ContactMessage,
    Camera, LiveDirector, DirectorRoom, StandbyImage, DirectorRoomCamera,
    ProgramRoom, PauseScreen, StreamOverlay, CutOutGraphic, StreamPreset,
    ContentSegment, ShowRundown
)
from .mail import send_booking_confirmation, send_invoice, send_booking_approved, send_new_booking_admin

admin.site.register(ProgramRoom)


class DirectorRoomCameraInline(admin.TabularInline):
    model = DirectorRoomCamera
    extra = 1
    autocomplete_fields = ['camera']
    ordering = ['order']


@admin.register(DirectorRoom)
class DirectorRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'is_streaming', 'stream_status_badge', 'camera_count', 'created_at']
    list_editable = ['is_active']
    list_filter = ['is_active', 'is_streaming', 'created_at']
    search_fields = ['name', 'description']
    inlines = [DirectorRoomCameraInline]
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Streaming-Konfiguration', {
            'fields': ('youtube_stream_key', 'twitch_stream_key'),
            'description': 'Stream-Keys für automatisches Streaming zu YouTube/Twitch'
        }),
        ('Status (wird automatisch aktualisiert)', {
            'fields': ('is_streaming', 'current_output'),
            'classes': ('collapse',)
        }),
    )
    
    def stream_status_badge(self, obj):
        if obj.is_streaming:
            return format_html('<span style="color:#28a745;font-weight:bold;">🔴 STREAMING</span>')
        return format_html('<span style="color:#6c757d;">⚫ Offline</span>')
    stream_status_badge.short_description = "Stream-Status"
    
    def camera_count(self, obj):
        count = obj.room_cameras.count()
        if count == 0:
            return format_html('<span style="color:#dc3545;">Keine Kameras</span>')
        return format_html('<span style="color:#28a745;">{} Kamera{}</span>', count, 's' if count != 1 else '')
    camera_count.short_description = "Kameras"


@admin.register(DirectorRoomCamera)
class DirectorRoomCameraAdmin(admin.ModelAdmin):
    list_display = ['room', 'camera', 'order']
    list_editable = ['order']
    list_filter = ['room']
    ordering = ['room', 'order']
    
    autocomplete_fields = ['camera']


@admin.register(StandbyImage)
class StandbyImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'image_preview', 'is_active', 'created_at']
    list_editable = ['is_active']
    list_filter = ['is_active']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:60px;border-radius:4px;">', obj.image.url)
        return "–"
    image_preview.short_description = "Vorschau"


# ── Logo ──────────────────────────────────────────────────────────────────
@admin.register(SenderLogo)
class SenderLogoAdmin(admin.ModelAdmin):
    list_display = ['logo_preview', 'position', 'scale', 'opacity', 'is_active', 'updated_at']
    list_editable = ['position', 'is_active']

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height:40px;border-radius:4px;">', obj.logo.url)
        return "–"
    logo_preview.short_description = "Vorschau"


# ── Kategorie ─────────────────────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'color']
    prepopulated_fields = {'slug': ('name',)}


# ── Videos ────────────────────────────────────────────────────────────────
@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'source_type', 'duration_display', 'category', 'allow_in_mediathek', 'is_active']
    list_filter = ['source_type', 'category', 'is_active', 'allow_in_mediathek']
    search_fields = ['title']
    list_editable = ['is_active', 'allow_in_mediathek']

    def duration_display(self, obj):
        return obj.duration_display()
    duration_display.short_description = 'Dauer'


# ── Werbevideos ───────────────────────────────────────────────────────────
@admin.register(AdVideo)
class AdVideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'ad_type', 'duration', 'advertisement', 'is_active']
    list_filter = ['ad_type', 'is_active']
    list_editable = ['is_active']
    search_fields = ['title']


@admin.register(AdBreakTemplate)
class AdBreakTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_duration', 'include_trailer', 'include_outro']


# ── Sendeplan ─────────────────────────────────────────────────────────────
class AdBreakInline(admin.TabularInline):
    model = AdBreak
    extra = 1
    fields = ['time_offset_seconds', 'max_duration', 'template', 'played']
    readonly_fields = ['played']


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['title', 'start_time', 'end_time', 'duration_minutes_display', 'category', 'is_active']
    list_filter = ['is_active', 'category', 'repeat']
    search_fields = ['title']
    inlines = [AdBreakInline]
    date_hierarchy = 'start_time'

    def duration_minutes_display(self, obj):
        return f"{obj.duration_minutes()} Min"
    duration_minutes_display.short_description = 'Dauer'


# ── Live-Streams ──────────────────────────────────────────────────────────
class LiveAdBreakInline(admin.TabularInline):
    model = LiveAdBreak
    extra = 0
    readonly_fields = ['started_at', 'ended_at', 'is_active']
    fields = ['template', 'max_duration', 'is_active', 'started_at', 'ended_at']



@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ['title', 'source_type', 'is_live', 'live_badge', 'ad_break_status', 'scheduled_start']
    list_editable = ['is_live']
    list_filter = ['source_type', 'is_live']
    inlines = [LiveAdBreakInline]

    def live_badge(self, obj):
        if obj.is_live:
            return format_html('<span style="color:#e63946;font-weight:bold;">🔴 LIVE</span>')
        return "–"
    live_badge.short_description = "Status"

    def ad_break_status(self, obj):
        ab = obj.get_active_ad_break()
        if ab:
            return format_html('<span style="color:#e63946;font-weight:bold;">🎯 WERBEPAUSE</span>')
        return format_html('<span style="color:#28a745;">✅ Normal</span>')

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('<int:pk>/go-live/', self.admin_site.admin_view(self.go_live)),
            path('<int:pk>/stop-live/', self.admin_site.admin_view(self.stop_live)),
        ]
        return extra + urls

    def go_live(self, request, pk):
        stream = LiveStream.objects.get(pk=pk)
        stream.is_live = True
        stream.save()
        self.message_user(request, "🔴 Stream ist LIVE", messages.SUCCESS)
        return redirect(f'/admin/tv/livestream/{pk}/change/')

    def stop_live(self, request, pk):
        stream = LiveStream.objects.get(pk=pk)
        stream.is_live = False
        stream.save()
        self.message_user(request, "⬛ Stream gestoppt", messages.SUCCESS)
        return redirect(f'/admin/tv/livestream/{pk}/change/')




# ── Werbung ───────────────────────────────────────────────────────────────
@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'title', 'status_display', 'paid', 'start_date', 'end_date', 'plays_display']
    list_filter = ['status', 'paid', 'timeslot']
    search_fields = ['company_name', 'title', 'email']
    list_editable = ['paid']
    readonly_fields = ['plays_count', 'id']

    def status_display(self, obj):
        colors = {
            'pending': '#ffc107', 'invoice_sent': '#17a2b8',
            'paid': '#6f42c1', 'active': '#28a745',
            'expired': '#6c757d', 'rejected': '#dc3545',
        }
        color = colors.get(obj.status, '#888')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'

    def plays_display(self, obj):
        pct = int(obj.plays_count / obj.max_plays * 100) if obj.max_plays else 0
        return format_html(
            '{}/{} <div style="background:#333;border-radius:3px;height:6px;width:100px;display:inline-block;vertical-align:middle;margin-left:6px;">'
            '<div style="background:#e63946;width:{}%;height:100%;border-radius:3px;"></div></div>',
            obj.plays_count, obj.max_plays, pct
        )
    plays_display.short_description = 'Einblendungen'

    def activate_action(self, request, queryset):
        for ad in queryset:
            ad.status = 'active'
            ad.paid = True
            ad.save()
    activate_action.short_description = "✅ Freischalten (aktiv setzen)"

    actions = ['activate_action']


@admin.register(AdBooking)
class AdBookingAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'package', 'email', 'price', 'paid_display', 'invoice_sent', 'created_at']
    list_filter = ['package', 'paid', 'invoice_sent']
    search_fields = ['company_name', 'customer_name', 'email']
    readonly_fields = ['created_at', 'price', 'advertisement']

    def paid_display(self, obj):
        if obj.paid:
            return format_html('<span style="color:#28a745;font-weight:bold;">✅ Bezahlt</span>')
        return format_html('<span style="color:#ffc107;font-weight:bold;">⏳ Offen</span>')
    paid_display.short_description = "Zahlung"

    def send_confirmation_action(self, request, queryset):
        for b in queryset:
            if send_booking_confirmation(b):
                b.booking_confirmation_sent = True
                b.save()
                self.message_user(request, f"✉️ Bestätigung gesendet an {b.email}", messages.SUCCESS)
    send_confirmation_action.short_description = "✉️ Buchungsbestätigung senden"

    def send_invoice_action(self, request, queryset):
        for b in queryset:
            if send_invoice(b):
                b.invoice_sent = True
                b.save()
                self.message_user(request, f"🧾 Rechnung gesendet an {b.email}", messages.SUCCESS)
    send_invoice_action.short_description = "🧾 Rechnung per E-Mail senden"

    def mark_paid_and_activate(self, request, queryset):
        for b in queryset:
            b.paid = True
            b.save()
            ad = b.activate_advertisement()
            send_booking_approved(b)
            self.message_user(request, f"✅ {b.company_name} freigeschaltet – Spot läuft auf RSL!", messages.SUCCESS)
    mark_paid_and_activate.short_description = "✅ Als bezahlt markieren & Spot freischalten"

    actions = ['send_confirmation_action', 'send_invoice_action', 'mark_paid_and_activate']


# ── Playlist ──────────────────────────────────────────────────────────────
class PlaylistEntryInline(admin.TabularInline):
    model = PlaylistEntry
    extra = 2


@admin.register(PlaylistItem)
class PlaylistItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'play_mode', 'is_active']
    list_editable = ['is_active']
    inlines = [PlaylistEntryInline]


# ── News & Kontakt ─────────────────────────────────────────────────────────
@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ['text', 'is_active', 'created_at', 'expires_at']
    list_editable = ['is_active']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at', 'read']
    list_editable = ['read']
    readonly_fields = ['name', 'email', 'subject', 'message', 'created_at']


# ── Kameras & Regie ───────────────────────────────────────────────────────
@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'stream_url_short', 'preview_image_available', 'is_active', 'order', 'assigned_rooms']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active', 'camera_type']  # camera_type hinzugefügt für bessere Filterung
    search_fields = ['name', 'stream_url']
    ordering = ['order', 'name']
    
    fieldsets = (
        ('Kamera-Informationen', {
            'fields': ('name', 'camera_type', 'is_active', 'order')
        }),
        ('Stream-URLs', {
            'fields': ('stream_url',),
            'description': 'stream_url: Haupt-Stream-URL (RTMP/RTSP/HLS)'
        }),
        ('Vorschau', {
            'fields': ('preview_image',),
            'description': 'Statisches Vorschaubild für den Admin-Bereich'
        }),
        ('Audio', {
            'fields': ('has_audio', 'audio_enabled'),
        }),
    )
    
    def stream_url_short(self, obj):
        url = obj.stream_url
        if len(url) > 50:
            return url[:47] + '...'
        return url
    stream_url_short.short_description = "Stream URL"
    
    def preview_image_available(self, obj):
        if obj.preview_image:
            return format_html('<span style="color:#28a745;">✅</span>')
        return format_html('<span style="color:#6c757d;">–</span>')
    preview_image_available.short_description = "Vorschau"
    
    def assigned_rooms(self, obj):
        rooms = DirectorRoomCamera.objects.filter(camera=obj).select_related('room')
        if not rooms:
            return format_html('<span style="color:#6c757d;">Nicht zugeordnet</span>')
        room_names = ', '.join([r.room.name for r in rooms])
        return format_html('<span style="color:#28a745;">{}</span>', room_names)
    assigned_rooms.short_description = "Zugeordnete Räume"


@admin.register(LiveDirector)
class LiveDirectorAdmin(admin.ModelAdmin):
    list_display = ['live_stream', 'selected_camera', 'updated_at']
    list_filter = ['live_stream']
    readonly_fields = ['updated_at']

# Füge dies zu tv/admin.py hinzu

from django.contrib import admin
from django.utils.html import format_html

@admin.register(PauseScreen)
class PauseScreenAdmin(admin.ModelAdmin):
    list_display = ['title', 'background_type', 'show_active_badge', 'preview_colors', 'created_at']
    list_filter = ['background_type', 'is_active', 'animation']
    search_fields = ['title', 'main_text', 'sub_text']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('title', 'is_active', 'is_default')
        }),
        ('Hintergrund', {
            'fields': ('background_type', 'color_primary', 'color_secondary', 'background_image')
        }),
        ('Text', {
            'fields': ('main_text', 'sub_text')
        }),
        ('Logo', {
            'fields': ('show_logo', 'custom_logo')
        }),
        ('Animation', {
            'fields': ('animation',)
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def show_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #2a9d8f; color: white; padding: 3px 10px; border-radius: 10px; font-weight: 600;">✓ AKTIV</span>'
            )
        return format_html(
            '<span style="background: #666; color: white; padding: 3px 10px; border-radius: 10px;">Inaktiv</span>'
        )
    show_active_badge.short_description = 'Status'
    
    def preview_colors(self, obj):
        if obj.background_type == 'gradient':
            return format_html(
                '<div style="display: flex; gap: 5px;">'
                '<div style="width: 30px; height: 30px; background: {}; border-radius: 4px; border: 1px solid #ddd;"></div>'
                '<div style="width: 30px; height: 30px; background: {}; border-radius: 4px; border: 1px solid #ddd;"></div>'
                '</div>',
                obj.color_primary, obj.color_secondary
            )
        elif obj.background_type == 'solid':
            return format_html(
                '<div style="width: 60px; height: 30px; background: {}; border-radius: 4px; border: 1px solid #ddd;"></div>',
                obj.color_primary
            )
        return '(Bild)'
    preview_colors.short_description = 'Vorschau'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_pause_screen']
    
    def activate_pause_screen(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "Bitte nur ein Pausenbild auswählen", level='error')
            return
        
        pause_screen = queryset.first()
        pause_screen.activate()
        self.message_user(request, f'"{pause_screen.title}" wurde aktiviert')
    activate_pause_screen.short_description = "Ausgewähltes Pausenbild aktivieren"


@admin.register(StreamOverlay)
class StreamOverlayAdmin(admin.ModelAdmin):
    list_display = ['name', 'overlay_type', 'position', 'show_active_badge', 'preview_style', 'duration']
    list_filter = ['overlay_type', 'position', 'is_active']
    search_fields = ['name', 'text_content']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'overlay_type', 'position', 'is_active')
        }),
        ('Design', {
            'fields': ('background_color', 'text_color', 'font_size')
        }),
        ('Content', {
            'fields': ('text_content', 'duration')
        }),
        ('Animation', {
            'fields': ('animation_in', 'animation_out')
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def show_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #2a9d8f; color: white; padding: 3px 10px; border-radius: 10px; font-weight: 600;">✓ AN</span>'
            )
        return format_html(
            '<span style="background: #666; color: white; padding: 3px 10px; border-radius: 10px;">AUS</span>'
        )
    show_active_badge.short_description = 'Status'
    
    def preview_style(self, obj):
        return format_html(
            '<div style="background: {}; color: {}; padding: 5px 10px; border-radius: 4px; font-size: {}px; display: inline-block;">'
            'Vorschau'
            '</div>',
            obj.background_color, obj.text_color, min(obj.font_size, 14)
        )
    preview_style.short_description = 'Stil-Vorschau'


@admin.register(CutOutGraphic)
class CutOutGraphicAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'show_thumbnail', 'hotkey', 'times_used', 'is_active']
    list_filter = ['category', 'is_active', 'can_animate']
    search_fields = ['name', 'hotkey']
    readonly_fields = ['times_used', 'created_at', 'created_by', 'show_preview']
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'category', 'image', 'show_preview', 'is_active')
        }),
        ('Position & Größe', {
            'fields': (
                ('default_x', 'default_y'),
                ('default_width', 'default_height')
            )
        }),
        ('Verhalten', {
            'fields': ('can_animate', 'animation_duration', 'hotkey')
        }),
        ('Statistik', {
            'fields': ('times_used',),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def show_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px; border-radius: 4px;">',
                obj.image.url
            )
        return '(Kein Bild)'
    show_thumbnail.short_description = 'Vorschau'
    
    def show_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">',
                obj.image.url
            )
        return '(Noch kein Bild hochgeladen)'
    show_preview.short_description = 'Bild-Vorschau'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StreamPreset)
class StreamPresetAdmin(admin.ModelAdmin):
    list_display = ['name', 'resolution', 'fps', 'bitrate', 'show_active_badge', 'created_at']
    list_filter = ['resolution', 'fps', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    filter_horizontal = ['overlays']
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Video-Einstellungen', {
            'fields': (
                ('resolution', 'fps'),
                'bitrate'
            )
        }),
        ('Audio-Einstellungen', {
            'fields': (
                ('audio_bitrate', 'audio_sample_rate'),
            )
        }),
        ('Szene & Overlays', {
            'fields': ('default_scene', 'overlays')
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def show_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #2a9d8f; color: white; padding: 3px 10px; border-radius: 10px; font-weight: 600;">✓ AKTIV</span>'
            )
        return format_html(
            '<span style="background: #666; color: white; padding: 3px 10px; border-radius: 10px;">Inaktiv</span>'
        )
    show_active_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_preset']
    
    def activate_preset(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "Bitte nur ein Preset auswählen", level='error')
            return
        
        preset = queryset.first()
        preset.activate()
        self.message_user(request, f'Preset "{preset.name}" wurde aktiviert')
    activate_preset.short_description = "Ausgewähltes Preset aktivieren"


# Erweitere bestehende ContentSegment Admin
@admin.register(ContentSegment)
class ContentSegmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'rundown', 'segment_type', 'show_duration', 'order', 'show_status', 'is_ready']
    list_filter = ['segment_type', 'is_ready', 'was_played', 'rundown']
    search_fields = ['title', 'description', 'script']
    readonly_fields = ['actual_duration', 'was_played', 'played_at', 'created_at', 'updated_at']
    list_editable = ['order']
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('title', 'segment_type', 'description', 'rundown', 'order')
        }),
        ('Timing', {
            'fields': (
                'planned_duration',
                'actual_duration'
            )
        }),
        ('Content', {
            'fields': ('video_file', 'video_url', 'scene')
        }),
        ('Skript & Notizen', {
            'fields': ('script', 'notes')
        }),
        ('Status', {
            'fields': ('is_ready', 'was_played', 'played_at')
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def show_duration(self, obj):
        mins = obj.planned_duration // 60
        secs = obj.planned_duration % 60
        return f"{mins}:{secs:02d}"
    show_duration.short_description = 'Dauer'
    
    def show_status(self, obj):
        if obj.was_played:
            return format_html(
                '<span style="background: #444; color: #999; padding: 3px 10px; border-radius: 10px;">✓ Gespielt</span>'
            )
        elif obj.is_ready:
            return format_html(
                '<span style="background: #2a9d8f; color: white; padding: 3px 10px; border-radius: 10px;">✓ Bereit</span>'
            )
        return format_html(
            '<span style="background: #666; color: white; padding: 3px 10px; border-radius: 10px;">○ Ausstehend</span>'
        )
    show_status.short_description = 'Status'


@admin.register(ShowRundown)
class ShowRundownAdmin(admin.ModelAdmin):
    list_display = ['title', 'show_date', 'show_total_duration', 'segment_count', 'show_status', 'is_live']
    list_filter = ['is_live', 'is_active', 'show_date']
    search_fields = ['title']
    readonly_fields = ['total_planned_duration', 'current_segment', 'created_at', 'updated_at', 'created_by']
    date_hierarchy = 'show_date'
    
    fieldsets = (
        ('Allgemein', {
            'fields': ('title', 'show_date', 'is_active')
        }),
        ('Status', {
            'fields': ('is_live', 'current_segment', 'total_planned_duration')
        }),
        ('Meta', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def show_total_duration(self, obj):
        hours = obj.total_planned_duration // 3600
        mins = (obj.total_planned_duration % 3600) // 60
        return f"{hours}h {mins}min"
    show_total_duration.short_description = 'Gesamt-Dauer'
    
    def segment_count(self, obj):
        return obj.segments.count()
    segment_count.short_description = 'Segmente'
    
    def show_status(self, obj):
        if obj.is_live:
            return format_html(
                '<span style="background: #e63946; color: white; padding: 3px 10px; border-radius: 10px; font-weight: 600;">● LIVE</span>'
            )
        elif obj.is_active:
            return format_html(
                '<span style="background: #2a9d8f; color: white; padding: 3px 10px; border-radius: 10px;">Aktiv</span>'
            )
        return format_html(
            '<span style="background: #666; color: white; padding: 3px 10px; border-radius: 10px;">Inaktiv</span>'
        )
    show_status.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['recalculate_duration']
    
    def recalculate_duration(self, request, queryset):
        for rundown in queryset:
            rundown.calculate_total_duration()
        self.message_user(request, f'{queryset.count()} Rundown(s) aktualisiert')
    recalculate_duration.short_description = "Dauer neu berechnen"