from urllib.parse import urlparse

from django import template
from django.utils import timezone

from rsl_tv.broadcast_api import youtube_id

register = template.Library()


@register.filter
def yt_id(url):
    return youtube_id(url) or ""


@register.filter
def embed_src(url):
    """YouTube-Links → datenschutzfreundliches Embed, sonst leerer String."""
    vid = youtube_id(url)
    if vid:
        return f"https://www.youtube-nocookie.com/embed/{vid}?rel=0&modestbranding=1"
    return ""


@register.filter
def domain(url):
    """'https://www.tagesschau.de/x/y' → 'tagesschau.de'"""
    host = urlparse(url or "").netloc
    return host[4:] if host.startswith("www.") else host


@register.filter
def hires(url):
    """YouTube-Vorschaubild in voller Auflösung (16:9, ohne schwarze Balken)."""
    if url and "i.ytimg.com" in url:
        return url.replace("hqdefault", "maxresdefault")
    return url


@register.filter
def is_direct_video(url):
    return bool(url) and url.split("?")[0].lower().endswith((".mp4", ".webm", ".m3u8", ".mov"))


@register.filter
def minutes(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    h, rest = divmod(seconds, 3600)
    m = rest // 60
    return f"{h} Std. {m} Min." if h else f"{max(m, 1)} Min."


@register.filter
def day_label(value):
    """'Heute', 'Morgen', 'Gestern' oder Wochentag + Datum."""
    if not value:
        return ""
    d = value.date() if hasattr(value, "date") and callable(value.date) else value
    today = timezone.localdate()
    delta = (d - today).days
    names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    if delta == 0:
        return "Heute"
    if delta == 1:
        return "Morgen"
    if delta == -1:
        return "Gestern"
    return f"{names[d.weekday()]}, {d.strftime('%d.%m.')}"
