"""
Werbemanager – steuert Werbespots, L-Werbung und Werbepausen des Studios
über die Ad-Manager-API (rsl_tv/ad_manager_api.py). Nur für Staff-Benutzer.
"""
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from rsl_tv import ad_manager_api as ads
from rsl_tv import broadcast_api as rsl_api

PAGE = 'werbemanager'


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _to_iso(value):
    """'2026-11-20T08:00' (datetime-local, deutsche Zeit) → ISO mit Zeitzone; leer → None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.isoformat()


def _to_local_input(value):
    """ISO aus der API → Wert für <input type="datetime-local">."""
    dt = rsl_api.parse_dt(value) if value else None
    return dt.strftime('%Y-%m-%dT%H:%M') if dt else ''


def _int(value, default=None, lo=None, hi=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _regions_or_empty(request):
    try:
        return ads.regions()
    except ads.AdManagerError as e:
        messages.warning(request, f"Regionen konnten nicht geladen werden: {e.message}")
        return []


def _with_dates(item, *keys):
    """Ergänzt *_dt (für Anzeige) und *_input (für Formulare)."""
    item = dict(item or {})
    for k in keys:
        item[f'{k}_dt'] = rsl_api.parse_dt(item.get(k)) if item.get(k) else None
        item[f'{k}_input'] = _to_local_input(item.get(k))
    return item


def _render(request, template, **ctx):
    ctx.setdefault('page', PAGE)
    ctx.setdefault('configured', ads.is_configured())
    ctx.setdefault('api_url', ads.API_URL)
    return render(request, f'tv/werbemanager/{template}', ctx)


def _upload_or_url(request, file_field, url_field, label):
    """Bevorzugt eine hochgeladene Datei, sonst die eingetragene URL."""
    f = request.FILES.get(file_field)
    if f:
        return ads.upload_file(f)
    url = request.POST.get(url_field, '').strip()
    if url and not url.startswith(('http://', 'https://')):
        raise ads.AdManagerError(f"{label}: Bitte eine gültige URL (https://…) angeben.")
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Übersicht
# ─────────────────────────────────────────────────────────────────────────────

def _first(d, *keys, default=None):
    """Erster vorhandene, nicht leere Wert – die API-Feldnamen sind nicht überall gleich."""
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if v not in (None, ''):
            return v
    return default


@staff_member_required
def dashboard(request):
    ctx = {'status': None, 'stats': [], 'spots': [], 'l_ads': [], 'error': None}
    if ads.is_configured():
        try:
            raw = ads.status() or {}
            current = raw.get('current_spot') if isinstance(raw.get('current_spot'), dict) else {}
            ctx['status'] = {
                'on_air': bool(_first(raw, 'ad_break_active', 'active', 'is_active', 'playing', 'is_playing', default=False)),
                'title': _first(current, 'title') or _first(raw, 'spot_title', 'title', default=''),
            }
            spots = ads.list_spots(limit=100)
            ctx['spots'] = spots
            ctx['l_ads'] = ads.list_l_ads()
            names = {s.get('id'): s.get('title') for s in spots}
            stats = []
            for row in ads.stats():
                last = _first(row, 'last_played_at')
                stats.append({
                    'title': _first(row, 'title', 'spot_title') or names.get(_first(row, 'spot_id', 'id')) or '–',
                    'plays': _first(row, 'plays', 'play_count', 'count', 'total', default=0),
                    'plays_today': _first(row, 'plays_today', 'play_count_today', default='–'),
                    'last_played_dt': rsl_api.parse_dt(last) if last else None,
                })
            stats.sort(key=lambda r: -(r['plays'] if isinstance(r['plays'], (int, float)) else 0))
            ctx['stats'] = stats[:15]
        except ads.AdManagerError as e:
            ctx['error'] = e.message
    ctx['active_spots'] = sum(1 for s in ctx['spots'] if s.get('is_active', True))
    ctx['active_l_ads'] = sum(1 for a in ctx['l_ads'] if a.get('is_active', True))
    return _render(request, 'dashboard.html', **ctx)


# ─────────────────────────────────────────────────────────────────────────────
# Werbespots
# ─────────────────────────────────────────────────────────────────────────────

@staff_member_required
def spot_list(request):
    filters = {
        'is_active': request.GET.get('is_active', ''),
        'spot_type': request.GET.get('spot_type', ''),
    }
    spots, error = [], None
    try:
        spots = [_with_dates(s, 'starts_at', 'expires_at') for s in ads.list_spots(limit=100, **filters)]
    except ads.AdManagerError as e:
        error = e.message
    spot_types = sorted({s.get('spot_type') for s in spots if s.get('spot_type')})
    return _render(request, 'spot_list.html', spots=spots, error=error, filters=filters, spot_types=spot_types)


@staff_member_required
def spot_edit(request, spot_id=None):
    spot = {}
    if spot_id:
        try:
            spot = ads.get_spot(spot_id) or {}
        except ads.AdManagerError as e:
            messages.error(request, e.message)
            return redirect('werbemanager_spots')

    if request.method == 'POST':
        try:
            video_url = _upload_or_url(request, 'video_file', 'video_url', 'Video')
            if not video_url and not spot_id:
                raise ads.AdManagerError("Bitte ein Video hochladen oder eine Video-URL angeben.")
            data = {
                'title': request.POST.get('title', '').strip(),
                'duration_seconds': _int(request.POST.get('duration_seconds'), 30, 1, 600),
                'starts_at': _to_iso(request.POST.get('starts_at')),
                'expires_at': _to_iso(request.POST.get('expires_at')),
                'target_regions': request.POST.getlist('target_regions'),
                'is_premium': bool(request.POST.get('is_premium')),
                'is_active': bool(request.POST.get('is_active')),
            }
            if video_url:
                data['video_url'] = video_url
            for field in ('weight', 'max_plays', 'cooldown_minutes'):
                n = _int(request.POST.get(field), None, 0)
                if n is not None:
                    data[field] = n
            if not data['title']:
                raise ads.AdManagerError("Bitte einen Titel angeben.")
            if spot_id:
                ads.update_spot(spot_id, data)
                messages.success(request, f"Spot „{data['title']}“ gespeichert.")
            else:
                ads.create_spot(data)
                messages.success(request, f"Spot „{data['title']}“ angelegt.")
            return redirect('werbemanager_spots')
        except ads.AdManagerError as e:
            messages.error(request, e.message)
            spot = {**spot, **request.POST.dict(), 'target_regions': request.POST.getlist('target_regions'),
                    'is_premium': bool(request.POST.get('is_premium')), 'is_active': bool(request.POST.get('is_active'))}
            spot['starts_at_input'] = request.POST.get('starts_at', '')
            spot['expires_at_input'] = request.POST.get('expires_at', '')
            return _render(request, 'spot_form.html', spot=spot, spot_id=spot_id, regions=_regions_or_empty(request))

    spot = _with_dates(spot, 'starts_at', 'expires_at')
    if not spot_id:
        spot.setdefault('is_active', True)
        spot.setdefault('duration_seconds', 30)
    return _render(request, 'spot_form.html', spot=spot, spot_id=spot_id, regions=_regions_or_empty(request))


@staff_member_required
@require_POST
def spot_deactivate(request, spot_id):
    try:
        ads.deactivate_spot(spot_id)
        messages.success(request, "Spot deaktiviert.")
    except ads.AdManagerError as e:
        messages.error(request, e.message)
    return redirect('werbemanager_spots')


# ─────────────────────────────────────────────────────────────────────────────
# L-Werbung
# ─────────────────────────────────────────────────────────────────────────────

@staff_member_required
def l_ad_list(request):
    l_ads, settings_, error = [], {}, None
    try:
        l_ads = [_with_dates(a, 'starts_at', 'expires_at') for a in ads.list_l_ads(request.GET.get('is_active', ''))]
        settings_ = ads.get_l_ad_settings()
    except ads.AdManagerError as e:
        error = e.message
    return _render(request, 'l_ad_list.html', l_ads=l_ads, settings=settings_, error=error,
                   is_active=request.GET.get('is_active', ''))


@staff_member_required
@require_POST
def l_ad_settings(request):
    data = {
        'l_ads_enabled': bool(request.POST.get('l_ads_enabled')),
        'l_ad_interval_minutes': _int(request.POST.get('l_ad_interval_minutes'), 15, 1, 1440),
        'l_ad_offset_minutes': _int(request.POST.get('l_ad_offset_minutes'), 0, 0, 1440),
    }
    try:
        ads.update_l_ad_settings(data)
        messages.success(request, "Takt der L-Werbung gespeichert.")
    except ads.AdManagerError as e:
        messages.error(request, e.message)
    return redirect('werbemanager_l_ads')


@staff_member_required
def l_ad_edit(request, ad_id=None):
    ad = {}
    if ad_id:
        try:
            ad = ads.get_l_ad(ad_id) or {}
        except ads.AdManagerError as e:
            messages.error(request, e.message)
            return redirect('werbemanager_l_ads')

    if request.method == 'POST':
        try:
            media_url = _upload_or_url(request, 'media_file', 'media_url', 'Motiv links')
            bottom_url = _upload_or_url(request, 'bottom_media_file', 'bottom_media_url', 'Motiv unten')
            if not media_url and not ad_id:
                raise ads.AdManagerError("Bitte das Motiv links (480×1080) hochladen oder eine URL angeben.")
            data = {
                'title': request.POST.get('title', '').strip(),
                'headline': request.POST.get('headline', '').strip(),
                'subline': request.POST.get('subline', '').strip(),
                'background_color': request.POST.get('background_color', '').strip() or None,
                'duration_seconds': _int(request.POST.get('duration_seconds'), 20, 10, 60),
                'weight': _int(request.POST.get('weight'), 1, 0),
                'starts_at': _to_iso(request.POST.get('starts_at')),
                'expires_at': _to_iso(request.POST.get('expires_at')),
                'target_regions': request.POST.getlist('target_regions'),
                'is_premium': bool(request.POST.get('is_premium')),
                'is_active': bool(request.POST.get('is_active')),
            }
            if media_url:
                data['media_url'] = media_url
            if request.POST.get('remove_bottom') and not request.FILES.get('bottom_media_file'):
                data['bottom_media_url'] = None
            elif bottom_url:
                data['bottom_media_url'] = bottom_url
            if not data['title']:
                raise ads.AdManagerError("Bitte einen Titel angeben.")
            if ad_id:
                ads.update_l_ad(ad_id, data)
                messages.success(request, f"L-Werbung „{data['title']}“ gespeichert.")
            else:
                ads.create_l_ad(data)
                messages.success(request, f"L-Werbung „{data['title']}“ angelegt.")
            return redirect('werbemanager_l_ads')
        except ads.AdManagerError as e:
            messages.error(request, e.message)
            ad = {**ad, **request.POST.dict(), 'target_regions': request.POST.getlist('target_regions'),
                  'is_premium': bool(request.POST.get('is_premium')), 'is_active': bool(request.POST.get('is_active'))}
            ad['starts_at_input'] = request.POST.get('starts_at', '')
            ad['expires_at_input'] = request.POST.get('expires_at', '')
            return _render(request, 'l_ad_form.html', ad=ad, ad_id=ad_id, regions=_regions_or_empty(request))

    ad = _with_dates(ad, 'starts_at', 'expires_at')
    if not ad_id:
        ad.setdefault('is_active', True)
        ad.setdefault('duration_seconds', 20)
        ad.setdefault('weight', 1)
        ad.setdefault('background_color', '#0a1220')
    return _render(request, 'l_ad_form.html', ad=ad, ad_id=ad_id, regions=_regions_or_empty(request))


@staff_member_required
@require_POST
def l_ad_deactivate(request, ad_id):
    try:
        ads.deactivate_l_ad(ad_id)
        messages.success(request, "L-Werbung deaktiviert.")
    except ads.AdManagerError as e:
        messages.error(request, e.message)
    return redirect('werbemanager_l_ads')


# ─────────────────────────────────────────────────────────────────────────────
# Werbepausen
# ─────────────────────────────────────────────────────────────────────────────

@staff_member_required
def break_list(request):
    program_id = request.GET.get('program_id', '')
    programs = sorted(
        [p for p in rsl_api.get_programs() if p['video_type'] != 'ai_news'],
        key=lambda p: (p['series_title'] or p['title']).lower() + f"{p['episode_number'] or 0:05d}")
    names = {p['id']: p['title'] for p in programs}
    breaks, error = [], None
    try:
        for b in ads.list_breaks(program_id or None):
            b = dict(b)
            b['program_title'] = names.get(b.get('program_id'), b.get('program_id') or b.get('schedule_id') or '–')
            breaks.append(b)
        breaks.sort(key=lambda b: (b['program_title'], b.get('trigger_at_minutes') or 0))
    except ads.AdManagerError as e:
        error = e.message
    return _render(request, 'break_list.html', breaks=breaks, programs=programs, program_id=program_id, error=error)


@staff_member_required
@require_POST
def break_save(request, break_id=None):
    data = {
        'trigger_at_minutes': _int(request.POST.get('trigger_at_minutes'), 0, 0, 1440),
        'duration_seconds': _int(request.POST.get('duration_seconds'), 120, 10, 3600),
    }
    program_id = request.POST.get('program_id', '').strip()
    try:
        if break_id:
            ads.update_break(break_id, data)
            messages.success(request, "Werbepause gespeichert.")
        else:
            if not program_id:
                raise ads.AdManagerError("Bitte eine Sendung auswählen.")
            ads.create_break({'program_id': program_id, **data})
            messages.success(request, "Werbepause angelegt.")
    except ads.AdManagerError as e:
        messages.error(request, e.message)
    return _back_to_breaks(request)


@staff_member_required
@require_POST
def break_delete(request, break_id):
    try:
        ads.delete_break(break_id)
        messages.success(request, "Werbepause gelöscht.")
    except ads.AdManagerError as e:
        messages.error(request, e.message)
    return _back_to_breaks(request)


def _back_to_breaks(request):
    url = reverse('werbemanager_breaks')
    back = request.POST.get('back_program_id', '')
    return redirect(f"{url}?{urlencode({'program_id': back})}" if back else url)
