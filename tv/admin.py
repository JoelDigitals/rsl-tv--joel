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
    Camera, LiveDirector, DirectorRoom, StandbyImage, DirectorRoomCamera
)
from .mail import send_booking_confirmation, send_invoice, send_booking_approved, send_new_booking_admin

admin.site.register(DirectorRoom)
admin.site.register(StandbyImage)
admin.site.register(DirectorRoomCamera)


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
    list_display = ['name', 'stream_url', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active']
    ordering = ['order', 'name']


@admin.register(LiveDirector)
class LiveDirectorAdmin(admin.ModelAdmin):
    list_display = ['live_stream', 'selected_camera', 'updated_at']
    list_filter = ['live_stream']
    readonly_fields = ['updated_at']