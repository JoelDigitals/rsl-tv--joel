"""
RSL Ad-Manager-API (v1) des Studios.

Externe Werbemanager legen hierüber Werbespots, L-Werbung und Werbepausen an.
Anmeldung: Authorization: Bearer rslad_…  – den Schlüssel im Studio-Admin unter
„Ad-Manager-API“ erzeugen und als Umgebungsvariable AD_MANAGER_API_KEY setzen.

Endpunkte (laut Studio):
  GET  /status                 Läuft gerade Werbung?
  GET  /stats                  Ausspielungen je Spot
  GET  /regions                Gültige Regionscodes
  POST /uploads                { filename, content_type } → upload_url (PUT) + public_url
  GET/POST /spots, GET/PATCH/DELETE /spots/:id
  GET/POST /l-ads, GET/PATCH/DELETE /l-ads/:id
  GET/PATCH /l-ad-settings
  GET/POST /breaks, GET/PATCH/DELETE /breaks/:id
"""
import logging
import mimetypes
import os

import requests

logger = logging.getLogger(__name__)

API_URL = os.environ.get(
    "AD_MANAGER_API_URL",
    "https://api.85-215-240-180.sslip.io/functions/v1/ad-manager-api",
).rstrip("/")
TIMEOUT = 20
UPLOAD_TIMEOUT = 600


class AdManagerError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.message = message
        self.status = status


def api_key():
    return os.environ.get("AD_MANAGER_API_KEY", "").strip()


def is_configured():
    return bool(api_key())


def _unwrap(payload):
    """Antworten kommen als {"data": …} oder direkt – beides akzeptieren."""
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _request(method, path, params=None, json=None):
    if not is_configured():
        raise AdManagerError("Kein API-Schlüssel hinterlegt (AD_MANAGER_API_KEY).")
    try:
        r = requests.request(
            method, API_URL + path, params=params, json=json, timeout=TIMEOUT,
            headers={"Authorization": f"Bearer {api_key()}", "Accept": "application/json"},
        )
    except requests.RequestException as e:
        logger.warning("Ad-Manager-API %s %s nicht erreichbar: %s", method, path, e)
        raise AdManagerError("Die Studio-API ist gerade nicht erreichbar.")
    try:
        body = r.json() if r.content else {}
    except ValueError:
        body = {}
    if r.status_code >= 400:
        msg = body.get("error") if isinstance(body, dict) else None
        details = body.get("details") if isinstance(body, dict) else None
        if isinstance(details, list) and details and isinstance(details[0], dict):
            msg = f"{msg or 'Fehler'}: {details[0].get('message', '')}".strip(": ")
        raise AdManagerError(msg or f"Fehler {r.status_code} von der Studio-API", r.status_code)
    return _unwrap(body)


def _as_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "spots", "l_ads", "breaks", "regions"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


# ── Status & Statistik ─────────────────────────────────────────────────────
def status():
    return _request("GET", "/status") or {}


def stats():
    return _as_list(_request("GET", "/stats"))


def regions():
    """Liste von (code, label)."""
    data = _request("GET", "/regions")
    if isinstance(data, dict) and not _as_list(data):
        return [(k, v if isinstance(v, str) else k) for k, v in data.items()]
    out = []
    for r in _as_list(data):
        if isinstance(r, str):
            out.append((r, r))
        elif isinstance(r, dict):
            code = r.get("code") or r.get("id") or r.get("value")
            if code:
                out.append((code, r.get("label") or r.get("name") or code))
    return out


# ── Uploads ────────────────────────────────────────────────────────────────
def upload_file(f):
    """Lädt eine hochgeladene Django-Datei ins Studio und gibt die öffentliche URL zurück."""
    content_type = getattr(f, "content_type", None) or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    data = _request("POST", "/uploads", json={"filename": f.name, "content_type": content_type}) or {}
    upload_url, public_url = data.get("upload_url"), data.get("public_url")
    if not upload_url or not public_url:
        raise AdManagerError("Die Studio-API hat keine Upload-Adresse geliefert.")
    try:
        f.seek(0)
        r = requests.put(upload_url, data=f, headers={"Content-Type": content_type}, timeout=UPLOAD_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Upload von %s fehlgeschlagen: %s", f.name, e)
        raise AdManagerError(f"Upload von „{f.name}“ fehlgeschlagen.")
    return public_url


# ── Spots ──────────────────────────────────────────────────────────────────
def list_spots(**filters):
    return _as_list(_request("GET", "/spots", params={k: v for k, v in filters.items() if v not in (None, "")}))


def get_spot(spot_id):
    return _request("GET", f"/spots/{spot_id}")


def create_spot(data):
    return _request("POST", "/spots", json=data)


def update_spot(spot_id, data):
    return _request("PATCH", f"/spots/{spot_id}", json=data)


def deactivate_spot(spot_id):
    return _request("DELETE", f"/spots/{spot_id}")


# ── L-Werbung ──────────────────────────────────────────────────────────────
def list_l_ads(is_active=None):
    params = {"is_active": is_active} if is_active not in (None, "") else None
    return _as_list(_request("GET", "/l-ads", params=params))


def get_l_ad(ad_id):
    return _request("GET", f"/l-ads/{ad_id}")


def create_l_ad(data):
    return _request("POST", "/l-ads", json=data)


def update_l_ad(ad_id, data):
    return _request("PATCH", f"/l-ads/{ad_id}", json=data)


def deactivate_l_ad(ad_id):
    return _request("DELETE", f"/l-ads/{ad_id}")


def get_l_ad_settings():
    return _request("GET", "/l-ad-settings") or {}


def update_l_ad_settings(data):
    return _request("PATCH", "/l-ad-settings", json=data)


# ── Werbepausen ────────────────────────────────────────────────────────────
def list_breaks(program_id=None):
    return _as_list(_request("GET", "/breaks", params={"program_id": program_id} if program_id else None))


def get_break(break_id):
    return _request("GET", f"/breaks/{break_id}")


def create_break(data):
    return _request("POST", "/breaks", json=data)


def update_break(break_id, data):
    return _request("PATCH", f"/breaks/{break_id}", json=data)


def delete_break(break_id):
    return _request("DELETE", f"/breaks/{break_id}")
