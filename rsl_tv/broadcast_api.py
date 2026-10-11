"""
RSL Broadcast-API – öffentliche Lese-API (v1) des RSL Studios.

Alle Abfragen laufen serverseitig, werden kurz gecacht und liefern bei
Fehlern leere Daten statt einer Exception. Die Mediathek funktioniert damit
auch dann, wenn die API einmal nicht erreichbar ist – lokale Serien und
Videos werden immer angezeigt.
"""
import logging
import re
from collections import OrderedDict
from datetime import datetime

import requests
from django.core.cache import cache
from django.utils import timezone
from django.utils.text import slugify

logger = logging.getLogger(__name__)

API_URL = "https://wknwmmjnecnrffucrprd.supabase.co/functions/v1/broadcast-api"
TIMEOUT = 8
MAX_LIMIT = 100
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")

# Cache-Dauer je Ressource (Sekunden)
CACHE_TTL = {
    "broadcast": 20,
    "studios": 30,
    "studio": 30,
    "schedule": 120,
    "news": 300,
    "library": 300,
    "programs": 600,
    "edition": 600,
    "branding": 3600,
}


def _fetch(resource, limit=MAX_LIMIT, offset=0, id=None):
    params = {"resource": resource, "limit": limit, "offset": offset}
    if id:
        params["id"] = id
    try:
        r = requests.get(API_URL, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("data")
    except (requests.RequestException, ValueError) as e:
        logger.warning("Broadcast-API %s fehlgeschlagen: %s", resource, e)
        return None


def _cached(key, ttl, loader, empty):
    data = cache.get(key)
    if data is not None:
        return data
    data = loader()
    if data is None:
        # Fehler nur kurz cachen, damit die Seite nicht bei jedem Aufruf hängt
        cache.set(key, empty, 30)
        return empty
    cache.set(key, data, ttl)
    return data


def _fetch_all(resource, max_items=1000):
    """Holt alle Seiten einer Listen-Ressource (limit max. 100)."""
    items, offset = [], 0
    while offset < max_items:
        page = _fetch(resource, limit=MAX_LIMIT, offset=offset)
        if page is None:
            return None if not items else items
        items.extend(page)
        if len(page) < MAX_LIMIT:
            break
        offset += MAX_LIMIT
    return items


def _list(resource):
    return _cached(f"rslapi:{resource}", CACHE_TTL[resource], lambda: _fetch_all(resource), [])


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timezone.localtime(dt) if timezone.is_aware(dt) else dt
    except ValueError:
        return None


def youtube_id(url):
    if not url:
        return None
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def is_uuid(value):
    return bool(value and UUID_RE.match(value))


def _fmt_duration(seconds):
    if not seconds:
        return ""
    seconds = int(round(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h} Std. {m} Min."
    if m:
        return f"{m} Min."
    return f"{s} Sek."


def _program_title(p):
    """Kürzt 'Serie – Folge 12: Titel' auf 'Titel', wenn die Serie bekannt ist."""
    title = (p.get("title") or "").strip()
    series = (p.get("series_title") or "").strip()
    if series and title.startswith(series):
        rest = title[len(series):].lstrip(" –-:")
        rest = re.sub(r"^(Staffel \d+\s*[–-]\s*)?", "", rest)
        rest = re.sub(r"^Folge \d+:\s*", "", rest)
        return rest or title
    return title


def _normalize_program(p):
    if not p:
        return None
    yt = youtube_id(p.get("video_url"))
    thumb = p.get("thumbnail_url") or (f"https://i.ytimg.com/vi/{yt}/hqdefault.jpg" if yt else "")
    minutes = p.get("duration_minutes") or 0
    return {
        "id": p.get("id"),
        "title": p.get("title") or "Ohne Titel",
        "short_title": _program_title(p),
        "description": p.get("description") or "",
        "thumbnail": thumb,
        "video_url": p.get("video_url") or "",
        "video_type": p.get("video_type") or "",
        "youtube_id": yt,
        "duration_minutes": minutes,
        "duration_display": f"{minutes} Min." if minutes else "",
        "category": p.get("category") or "",
        "series_title": p.get("series_title") or "",
        "series_slug": slugify(p.get("series_title") or ""),
        "season_number": p.get("season_number"),
        "episode_number": p.get("episode_number"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Öffentliche Funktionen
# ─────────────────────────────────────────────────────────────────────────────

def get_programs():
    return [p for p in (_normalize_program(x) for x in _list("programs")) if p]


def get_program(program_id):
    return next((p for p in get_programs() if p["id"] == program_id), None)


def get_api_series():
    """Gruppiert Programme mit series_title zu Serien (sortiert nach Folge)."""
    groups = OrderedDict()
    for p in get_programs():
        if not p["series_title"]:
            continue
        g = groups.setdefault(p["series_slug"], {
            "slug": p["series_slug"],
            "title": p["series_title"],
            "category": p["category"],
            "episodes": [],
        })
        g["episodes"].append(p)
    result = []
    for g in groups.values():
        g["episodes"].sort(key=lambda e: (e["season_number"] or 0, e["episode_number"] or 0))
        g["thumbnail"] = next((e["thumbnail"] for e in g["episodes"] if e["thumbnail"]), "")
        g["description"] = next((e["description"] for e in g["episodes"] if e["description"]), "")
        g["count"] = len(g["episodes"])
        seasons = OrderedDict()
        for e in g["episodes"]:
            seasons.setdefault(e["season_number"] or 1, []).append(e)
        g["seasons"] = [{"number": n, "episodes": eps} for n, eps in seasons.items()]
        result.append(g)
    result.sort(key=lambda g: g["title"].lower())
    return result


def get_api_series_by_slug(slug):
    return next((s for s in get_api_series() if s["slug"] == slug), None)


def get_single_programs():
    """Programme ohne Serie (z. B. Musik, Story Times) – ohne KI-Nachrichten."""
    return [p for p in get_programs() if not p["series_title"] and p["video_type"] != "ai_news"]


def get_categories():
    cats = OrderedDict()
    for p in get_programs():
        if p["category"] and p["video_type"] != "ai_news":
            cats[slugify(p["category"])] = p["category"]
    return [{"slug": k, "name": v} for k, v in sorted(cats.items(), key=lambda x: x[1].lower())]


def get_library():
    """Ausgestrahlte Sendungen zum Nachschauen (neueste zuerst)."""
    items = []
    for x in _list("library"):
        prog = _normalize_program(x.get("programs")) or {}
        title = x.get("display_title_override") or prog.get("title") or "Sendung"
        items.append({
            "id": x.get("id"),
            "title": title,
            "short_title": x.get("display_title_override") or prog.get("short_title") or title,
            "series_title": prog.get("series_title", ""),
            "thumbnail": prog.get("thumbnail", ""),
            "duration_display": prog.get("duration_display", ""),
            "program": prog,
            "aired_at": parse_dt(x.get("start_time")),
            "embed_url": x.get("embed_url") or "",
        })
    items.sort(key=lambda i: i["aired_at"] or timezone.now(), reverse=True)
    return items


def get_library_item(item_id):
    return next((i for i in get_library() if i["id"] == item_id), None)


def get_news():
    """Nachrichten-Ausgaben der letzten 14 Tage."""
    items = []
    for x in _list("news"):
        prog = x.get("programs") or {}
        items.append({
            "id": x.get("id"),
            "title": prog.get("title") or "RSL Nachrichten",
            "thumbnail": prog.get("thumbnail_url") or "",
            "created_at": parse_dt(x.get("created_at")),
            "duration_display": _fmt_duration(x.get("audio_duration_seconds")),
            "embed_url": x.get("embed_url") or "",
        })
    items.sort(key=lambda i: i["created_at"] or timezone.now(), reverse=True)
    return items


def get_edition(edition_id):
    if not is_uuid(edition_id):
        return None
    data = _cached(f"rslapi:edition:{edition_id}", CACHE_TTL["edition"],
                   lambda: _fetch("edition", id=edition_id), {})
    if not data:
        return None
    meta = next((n for n in get_news() if n["id"] == edition_id), {})
    stories = []
    for it in data.get("items") or []:
        text = (it.get("text") or "").strip()
        stories.append({
            "kind": it.get("kind") or "report",
            "headline": it.get("headline") or "",
            "paragraphs": [p.strip() for p in text.split("\n\n") if p.strip()],
            "image_url": it.get("image_url") or "",
            "source_url": it.get("source_url") or "",
            "weather": it.get("weather"),
            "start_seconds": it.get("start_seconds"),
        })
    return {
        "id": data.get("id"),
        "title": meta.get("title") or "RSL Nachrichten",
        "created_at": parse_dt(data.get("created_at")),
        "intro_text": data.get("intro_text") or "",
        "outro_text": data.get("outro_text") or "",
        "stories": stories,
        "audio_url": data.get("audio_url") or "",
        "duration_display": _fmt_duration(data.get("audio_duration_seconds")),
        "embed_url": data.get("embed_url") or "",
    }


def get_schedule():
    items = []
    now = timezone.now()
    for x in _list("schedule"):
        prog = _normalize_program(x.get("programs")) or {}
        start, end = parse_dt(x.get("start_time")), parse_dt(x.get("end_time"))
        if not start:
            continue
        items.append({
            "id": x.get("id"),
            "title": x.get("display_title_override") or prog.get("title") or "Sendung",
            "short_title": x.get("display_title_override") or prog.get("short_title") or "Sendung",
            "series_title": prog.get("series_title", ""),
            "category": prog.get("category", ""),
            "thumbnail": prog.get("thumbnail", ""),
            "program_id": x.get("program_id"),
            "is_repeat": bool(x.get("is_repeat")),
            "start": start,
            "end": end,
            "is_now": bool(end and start <= now < end),
            "is_past": bool(end and end <= now),
        })
    items.sort(key=lambda i: i["start"])
    return items


def get_schedule_by_day():
    days = OrderedDict()
    for item in get_schedule():
        days.setdefault(item["start"].date(), []).append(item)
    return [{"date": d, "shows": shows} for d, shows in days.items()]


def get_now_and_next(count=5):
    sched = [s for s in get_schedule() if not s["is_past"]]
    current = next((s for s in sched if s["is_now"]), None)
    upcoming = [s for s in sched if not s["is_now"]][:count]
    return current, upcoming


def get_broadcast():
    data = _cached("rslapi:broadcast", CACHE_TTL["broadcast"], lambda: _fetch("broadcast", limit=1), [])
    return data[0] if data else {}


def get_studios():
    studios = []
    for s in _list("studios"):
        studios.append({
            "id": s.get("id"),
            "name": s.get("name") or "Studio",
            "description": s.get("description") or "",
            "is_active": bool(s.get("is_active")),
            "output_target": s.get("output_target") or "",
            "live_started_at": parse_dt(s.get("live_started_at")),
            "scheduled_start_at": parse_dt(s.get("scheduled_start_at")),
            "scheduled_title": s.get("scheduled_title") or "",
            "embed_url": s.get("embed_url") or "",
        })
    return studios


def get_studio(studio_id):
    return next((s for s in get_studios() if s["id"] == studio_id), None)


def get_branding():
    data = _cached("rslapi:branding", CACHE_TTL["branding"], lambda: _fetch("branding", limit=1), [])
    return data[0] if data else {}


def search(query):
    q = (query or "").lower().strip()
    if not q:
        return [], []
    programs = [p for p in get_programs() if p["video_type"] != "ai_news" and (
        q in p["title"].lower() or q in p["description"].lower()
        or q in p["series_title"].lower() or q in p["category"].lower())]
    series = [s for s in get_api_series() if q in s["title"].lower()]
    return series, programs
