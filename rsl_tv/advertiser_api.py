"""
Werbekonten des Studios für die RSL-TV-Website.

Kunden registrieren sich und melden sich mit demselben Konto an wie im Studio (/werbung).
Die Website hält nur die Anmelde-Tokens in der Django-Session und ruft die Studio-API mit dem
Token des Kunden auf. So prüft die Studio-Datenbank (RLS) selbst, dass jeder nur seine eigenen
Buchungen sieht; die Website bekommt dafür keinen Admin- oder Service-Schlüssel.
"""
import logging
import os
import re
import time
import uuid

import requests

logger = logging.getLogger(__name__)

STUDIO_URL = os.environ.get("STUDIO_SUPABASE_URL", "https://api.85-215-240-180.sslip.io").rstrip("/")
# Öffentlicher (anon) Schlüssel – steht ohnehin im Studio-Frontend; gibt ohne Login keine Kundendaten frei.
ANON_KEY = os.environ.get("STUDIO_SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzkyODYxOTM1LCJleHAiOjE5NTA1NDE5MzV9.O_fyLNruf3aFwx3MPIkdtt8ybLwUgaOWylBNml19htU").strip()
TIMEOUT = 20
UPLOAD_TIMEOUT = 900
SESSION_KEY = "studio_advertiser"

REGION_CHOICES = [
    ("DE", "Ganz Deutschland"), ("AT", "Österreich"), ("CH", "Schweiz"),
    ("DE-BW", "Baden-Württemberg"), ("DE-BY", "Bayern"), ("DE-BE", "Berlin"), ("DE-BB", "Brandenburg"),
    ("DE-HB", "Bremen"), ("DE-HH", "Hamburg"), ("DE-HE", "Hessen"), ("DE-MV", "Mecklenburg-Vorpommern"),
    ("DE-NI", "Niedersachsen"), ("DE-NW", "Nordrhein-Westfalen"), ("DE-RP", "Rheinland-Pfalz"), ("DE-SL", "Saarland"),
    ("DE-SN", "Sachsen"), ("DE-ST", "Sachsen-Anhalt"), ("DE-SH", "Schleswig-Holstein"), ("DE-TH", "Thüringen"),
]
SLOTS = ["Ganztägig", "Tagsüber", "Vorabend", "Primetime 20:15"]
BOOKING_COLUMNS = ("id,ad_title,status,created_at,start_date,end_date,desired_slot,plays_per_day,"
                   "spot_duration_seconds,spot_video_url,spot_id,admin_note,target_labels,price_cents,is_premium")


class AdvertiserError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.message = message
        self.status = status


def is_configured():
    return bool(ANON_KEY)


def _message(body, status):
    if isinstance(body, dict):
        msg = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error")
        details = body.get("details")
        if isinstance(details, list) and details and isinstance(details[0], dict):
            msg = f"{msg or 'Fehler'}: {details[0].get('message', '')}".strip(": ")
        if msg:
            return _translate(str(msg))
    return f"Fehler {status} vom Studio"


def _translate(msg):
    known = {
        "Invalid login credentials": "E-Mail oder Passwort ist falsch.",
        "Email not confirmed": "Bitte zuerst die E-Mail-Adresse über den Link in der Bestätigungs-Mail bestätigen.",
        "User already registered": "Für diese E-Mail gibt es schon ein Konto – bitte anmelden.",
    }
    for en, de in known.items():
        if en.lower() in msg.lower():
            return de
    return msg


def _call(method, path, token=None, **kwargs):
    if not is_configured():
        raise AdvertiserError("Werbekonten sind auf dieser Website noch nicht eingerichtet (STUDIO_SUPABASE_ANON_KEY fehlt).")
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {token or ANON_KEY}", "Accept": "application/json"}
    headers.update(kwargs.pop("headers", {}))
    try:
        r = requests.request(method, STUDIO_URL + path, headers=headers, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    except requests.RequestException as e:
        logger.warning("Studio %s %s nicht erreichbar: %s", method, path, e)
        raise AdvertiserError("Das Studio ist gerade nicht erreichbar – bitte später erneut versuchen.")
    try:
        body = r.json() if r.content else None
    except ValueError:
        body = None
    if r.status_code >= 400:
        raise AdvertiserError(_message(body, r.status_code), r.status_code)
    return body


# ── Anmeldung ────────────────────────────────────────────────────────────────
def _store(session, auth):
    if not auth or not auth.get("access_token"):
        return None
    user = auth.get("user") or {}
    session[SESSION_KEY] = {
        "access_token": auth["access_token"],
        "refresh_token": auth.get("refresh_token"),
        "expires_at": int(time.time()) + int(auth.get("expires_in") or 3600),
        "user_id": user.get("id"),
        "email": user.get("email"),
    }
    session.modified = True
    return session[SESSION_KEY]


def signup(session, email, password, company_name, contact_name="", phone="", redirect_to=None):
    """Legt ein Werbekonto an. Gibt True zurück, wenn direkt angemeldet, sonst muss die E-Mail bestätigt werden."""
    payload = {"email": email, "password": password,
               "data": {"account_type": "advertiser", "company_name": company_name, "contact_name": contact_name, "phone": phone}}
    params = {"redirect_to": redirect_to} if redirect_to else None
    body = _call("POST", "/auth/v1/signup", json=payload, params=params) or {}
    if body.get("access_token"):
        _store(session, body)
        return True
    return False


def login(session, email, password):
    body = _call("POST", "/auth/v1/token", params={"grant_type": "password"}, json={"email": email, "password": password})
    return _store(session, body)


def logout(session):
    acc = session.pop(SESSION_KEY, None)
    if acc:
        try:
            _call("POST", "/auth/v1/logout", token=acc["access_token"])
        except AdvertiserError:
            pass


def current(session):
    """Angemeldetes Konto aus der Session; erneuert das Token kurz vor Ablauf. None, wenn nicht angemeldet."""
    acc = session.get(SESSION_KEY)
    if not acc:
        return None
    if acc.get("expires_at", 0) - 60 < time.time():
        try:
            body = _call("POST", "/auth/v1/token", params={"grant_type": "refresh_token"}, json={"refresh_token": acc.get("refresh_token")})
            acc = _store(session, body)
        except AdvertiserError:
            session.pop(SESSION_KEY, None)
            return None
    return acc


# ── Konto & Buchungen (alles mit dem Token des Kunden → RLS) ────────────────
def is_advertiser(acc):
    return bool(_call("POST", "/rest/v1/rpc/is_advertiser", token=acc["access_token"], json={"_user_id": acc["user_id"]}))


def claim_account(acc, company_name):
    _call("POST", "/rest/v1/rpc/claim_advertiser_account", token=acc["access_token"], json={"_company_name": company_name})


def profile(acc):
    rows = _call("GET", "/rest/v1/advertiser_profiles", token=acc["access_token"],
                 params={"select": "company_name,contact_name,phone", "user_id": f"eq.{acc['user_id']}"}) or []
    return rows[0] if rows else {}


def my_bookings(acc):
    rows = _call("GET", "/rest/v1/ad_bookings", token=acc["access_token"],
                 params={"select": BOOKING_COLUMNS, "owner_id": f"eq.{acc['user_id']}", "order": "created_at.desc"}) or []
    spot_ids = [b["spot_id"] for b in rows if b.get("spot_id")]
    active = {}
    if spot_ids:
        spots = _call("GET", "/rest/v1/ad_spots", token=acc["access_token"],
                      params={"select": "id,is_active", "id": f"in.({','.join(spot_ids)})"}) or []
        active = {s["id"]: bool(s.get("is_active")) for s in spots}
    for b in rows:
        b["spot_active"] = active.get(b.get("spot_id")) if b.get("spot_id") else None
    return rows


def booking_stats(acc, booking_id):
    return _call("POST", "/rest/v1/rpc/own_ad_booking_stats", token=acc["access_token"],
                 json={"_booking_id": booking_id, "_days": 30}) or {}


def set_paused(acc, booking_id, paused):
    _call("POST", "/rest/v1/rpc/set_own_ad_booking_paused", token=acc["access_token"],
          json={"_booking_id": booking_id, "_paused": bool(paused)})


def withdraw(acc, booking_id):
    _call("POST", "/rest/v1/rpc/withdraw_own_ad_booking", token=acc["access_token"], json={"_booking_id": booking_id})


def create_booking(acc, data):
    """Bucht über die Studio-Function ad-booking; Preis und Eigentümer setzt das Studio selbst."""
    return _call("POST", "/functions/v1/ad-booking", token=acc["access_token"], json=data) or {}


def upload_spot(acc, django_file):
    """Lädt die geprüfte MP4 in den eigenen Ordner ad-videos/advertisers/<user_id>/ und gibt die öffentliche URL zurück."""
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(django_file.name)[0]).strip("-")[:60] or "spot"
    path = f"advertisers/{acc['user_id']}/{uuid.uuid4()}-{base}.mp4"
    django_file.seek(0)
    _call("POST", f"/storage/v1/object/ad-videos/{path}", token=acc["access_token"], data=django_file,
          headers={"Content-Type": "video/mp4", "x-upsert": "false"}, timeout=UPLOAD_TIMEOUT)
    return f"{STUDIO_URL}/storage/v1/object/public/ad-videos/{path}"


# ── Formatprüfung der MP4 (wie im Studio: H.264, Faststart, max. 1920×1080, 5–120 s) ──
MAX_UPLOAD_BYTES = 300 * 1024 * 1024


def inspect_mp4(f):
    """Liest nur Box-Header und moov. Liefert dict mit is_mp4, faststart, codec, width, height, duration."""
    f.seek(0, os.SEEK_END)
    size = f.tell()
    order, moov = [], None
    offset = 0
    while offset + 8 <= size and len(order) < 64:
        f.seek(offset)
        head = f.read(16)
        if len(head) < 8:
            break
        box_size = int.from_bytes(head[0:4], "big")
        box_type = head[4:8].decode("latin-1")
        if box_size == 1 and len(head) >= 16:
            box_size = int.from_bytes(head[8:16], "big")
        elif box_size == 0:
            box_size = size - offset
        if box_size < 8 or not re.fullmatch(r"[\x20-\x7e]{4}", box_type):
            break
        order.append(box_type)
        if box_type == "moov":
            moov = (offset, box_size)
        offset += box_size
    info = {"is_mp4": bool(order) and order[0] == "ftyp", "faststart": False, "codec": None, "width": 0, "height": 0, "duration": 0.0}
    if "moov" in order and "mdat" in order:
        info["faststart"] = order.index("moov") < order.index("mdat")
    if moov and moov[1] <= 64 * 1024 * 1024:
        f.seek(moov[0])
        data = f.read(moov[1])
        positions = {c: data.find(c.encode()) for c in ("avc1", "avc3", "hvc1", "hev1", "av01", "vp09", "mp4v")}
        found = [(p, c) for c, p in positions.items() if p >= 0]
        if found:
            info["codec"] = min(found)[1]
        i = data.find(b"mvhd")
        if i >= 0:
            version = data[i + 4]
            if version == 1:
                timescale = int.from_bytes(data[i + 24:i + 28], "big")
                duration = int.from_bytes(data[i + 28:i + 36], "big")
            else:
                timescale = int.from_bytes(data[i + 16:i + 20], "big")
                duration = int.from_bytes(data[i + 20:i + 24], "big")
            if timescale:
                info["duration"] = duration / timescale
        # Größte Spur-Abmessung aus den tkhd-Boxen (letzte 8 Bytes: Breite/Höhe als 16.16).
        start = 0
        while True:
            j = data.find(b"tkhd", start)
            if j < 0:
                break
            box_start = j - 4
            box_len = int.from_bytes(data[box_start:j], "big")
            end = box_start + box_len
            if 8 < box_len and end <= len(data):
                w = int.from_bytes(data[end - 8:end - 4], "big") >> 16
                h = int.from_bytes(data[end - 4:end], "big") >> 16
                if w * h > info["width"] * info["height"]:
                    info["width"], info["height"] = w, h
            start = j + 4
    f.seek(0)
    return info


def creative_errors(info, size):
    errors = []
    if not info["is_mp4"]:
        errors.append("Die Datei ist kein MP4-Video.")
    if size > MAX_UPLOAD_BYTES:
        errors.append("Die Datei ist größer als 300 MB.")
    if not info["codec"]:
        errors.append("Kein H.264-Videostream gefunden.")
    elif info["codec"] not in ("avc1", "avc3"):
        errors.append(f"Video-Codec {info['codec']} wird nicht unterstützt – bitte als H.264 exportieren.")
    if info["is_mp4"] and not info["faststart"]:
        errors.append("Die MP4 ist nicht für Streaming optimiert (beim Export „Web optimiert“/Faststart aktivieren).")
    if info["width"] > 1920 or info["height"] > 1080:
        errors.append(f"Auflösung {info['width']}×{info['height']} ist zu groß – höchstens 1920×1080.")
    if info["duration"] and not (5 <= info["duration"] <= 120):
        errors.append(f"Länge {round(info['duration'])} s – erlaubt sind 5–120 Sekunden.")
    return errors
