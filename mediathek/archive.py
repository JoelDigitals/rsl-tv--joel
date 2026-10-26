"""
Archiv der Mediathek: speichert Ausstrahlungen aus der RSL Broadcast-API
dauerhaft in der Datenbank (Modell ArchivedBroadcast).

- Ausgestrahlte Sendungen (resource=library) bleiben gespeichert, auch wenn
  die API sie nicht mehr liefert.
- Live-Streams der Studios (resource=studios) werden beim Start als
  Live-Stream angelegt und beim Ende mit Endzeit abgeschlossen.

sync() läuft automatisch beim Aufruf der Mediathek (höchstens alle
SYNC_INTERVAL Sekunden) und per Befehl: python manage.py sync_mediathek
"""
import logging

from django.core.cache import cache
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from rsl_tv import broadcast_api as rsl_api
from .models import ArchivedBroadcast

logger = logging.getLogger(__name__)

SYNC_INTERVAL = 120
_SYNC_KEY = "mediathek:archive:last-sync"


def available():
    """True, wenn die Archiv-Tabelle existiert (Migration 0003 ausgeführt).

    Fehlt sie, zeigt die Mediathek die Sendungen direkt aus der API an,
    statt mit einem Datenbankfehler abzustürzen.
    """
    ok = cache.get("mediathek:archive:available")
    if ok is None:
        try:
            ok = ArchivedBroadcast._meta.db_table in connection.introspection.table_names()
        except DatabaseError:
            ok = False
        if not ok:
            logger.error("Tabelle %s fehlt – bitte 'python manage.py migrate' ausführen.",
                         ArchivedBroadcast._meta.db_table)
        cache.set("mediathek:archive:available", ok, 300 if ok else 60)
    return ok


def sync(force=False):
    """Gleicht API und Archiv ab. Gibt (neu_sendungen, neu_live, beendet) zurück."""
    if not available():
        return 0, 0, 0
    if not force and cache.get(_SYNC_KEY):
        return 0, 0, 0
    cache.set(_SYNC_KEY, True, SYNC_INTERVAL)
    try:
        with transaction.atomic():
            new_items = _sync_library()
            new_live, ended = _sync_live()
        return new_items, new_live, ended
    except DatabaseError as e:
        logger.warning("Mediathek-Archiv konnte nicht synchronisiert werden: %s", e)
        return 0, 0, 0


def _sync_library():
    items = rsl_api.get_library()
    if not items:
        return 0
    known = set(ArchivedBroadcast.objects.filter(
        api_id__in=[i["id"] for i in items]).values_list("api_id", flat=True))
    new = []
    for i in items:
        if not i["id"] or i["id"] in known:
            continue
        prog = i["program"] or {}
        new.append(ArchivedBroadcast(
            api_id=i["id"],
            kind=ArchivedBroadcast.KIND_SENDUNG,
            title=(i["short_title"] or i["title"])[:500],
            series_title=(i["series_title"] or "")[:255],
            description=prog.get("description", ""),
            thumbnail=i["thumbnail"] or "",
            embed_url=i["embed_url"] or "",
            video_url=prog.get("video_url", ""),
            program_id=prog.get("id") or "",
            aired_at=i["aired_at"],
            duration_minutes=prog.get("duration_minutes") or 0,
        ))
    ArchivedBroadcast.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)


def _sync_live():
    studios = rsl_api.get_studios()
    if not studios:
        # API nicht erreichbar oder leer – laufende Streams nicht fälschlich beenden
        return 0, 0
    now = timezone.now()
    running_ids, created = [], 0
    for s in studios:
        if not (s["is_active"] and s["live_started_at"]):
            continue
        api_id = f"live:{s['id']}:{s['live_started_at'].isoformat()}"
        running_ids.append(api_id)
        _, was_created = ArchivedBroadcast.objects.get_or_create(
            api_id=api_id,
            defaults={
                "kind": ArchivedBroadcast.KIND_LIVE,
                "title": (s["scheduled_title"] or s["name"])[:500],
                "series_title": f"Studio {s['name']}"[:255],
                "description": s["description"],
                "embed_url": s["embed_url"],
                "studio_id": s["id"],
                "aired_at": s["live_started_at"],
            },
        )
        created += was_created
    ended = (ArchivedBroadcast.objects
             .filter(kind=ArchivedBroadcast.KIND_LIVE, ended_at__isnull=True)
             .exclude(api_id__in=running_ids)
             .update(ended_at=now))
    return created, ended


def as_items(objs):
    programs = {p["id"]: p for p in rsl_api.get_programs()}
    return [as_item(o, programs) for o in objs]


def as_item(obj, programs=None):
    """Archiv-Eintrag im selben Format wie broadcast_api.get_library()."""
    if programs is None:
        programs = {p["id"]: p for p in rsl_api.get_programs()}
    prog = programs.get(obj.program_id) if obj.program_id else None
    if not prog:
        yt = rsl_api.youtube_id(obj.video_url)
        prog = {
            "id": obj.program_id, "title": obj.title, "short_title": obj.title,
            "description": obj.description, "thumbnail": obj.thumbnail,
            "video_url": obj.video_url, "youtube_id": yt,
            "series_title": obj.series_title, "series_slug": "",
            "duration_display": obj.duration_display,
        }
    return {
        "id": obj.api_id,
        "pk": obj.pk,
        "kind": obj.kind,
        "title": obj.title,
        "short_title": obj.title,
        "series_title": obj.series_title,
        "thumbnail": obj.thumbnail or prog.get("thumbnail", ""),
        "duration_display": obj.duration_display,
        "program": prog,
        "aired_at": obj.aired_at,
        "ended_at": obj.ended_at,
        "is_running": obj.is_running,
        "embed_url": rsl_api.fix_embed(obj.embed_url),
        "studio_id": obj.studio_id,
    }


def sendungen():
    return ArchivedBroadcast.objects.filter(kind=ArchivedBroadcast.KIND_SENDUNG, is_active=True)


def live_streams():
    return ArchivedBroadcast.objects.filter(kind=ArchivedBroadcast.KIND_LIVE, is_active=True)
