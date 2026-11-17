"""
Werbekonto für Kunden auf der RSL-TV-Website (/werbung/konto/).

Gleiches Konto wie im Studio-AD-Manager: registrieren, anmelden, eigenen Spot hochladen,
Buchungen anlegen und nur die eigenen Buchungen sehen, pausieren, zurückziehen und auswerten.
Alle Daten kommen mit dem Token des Kunden aus dem Studio (Zugriffsregeln dort per RLS).
"""
from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from rsl_tv import advertiser_api as acct

PAGE = 'werbung'
STATUS = {
    'pending': ('Wird geprüft', 'warning'),
    'approved': ('Freigegeben', 'success'),
    'rejected': ('Abgelehnt', 'danger'),
    'aired': ('Gesendet', 'secondary'),
}


def _render(request, template, **ctx):
    ctx.setdefault('page', PAGE)
    ctx.setdefault('konto', acct.current(request.session))
    return render(request, f'tv/werbekonto/{template}', ctx)


def advertiser_required(view):
    """Angemeldet + Werbekunden-Rolle; sonst Login bzw. Konto aktivieren."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        konto = acct.current(request.session)
        if not konto:
            return redirect(f"/werbung/konto/login/?next={request.path}")
        try:
            if not acct.is_advertiser(konto):
                return redirect('werbekonto_aktivieren')
        except acct.AdvertiserError as e:
            messages.error(request, e.message)
            return redirect('werbung')
        request.werbekonto = konto
        return view(request, *args, **kwargs)
    return wrapper


def _safe_next(value):
    return value if value and value.startswith('/') and not value.startswith('//') else '/werbung/konto/'


def login_view(request):
    if acct.current(request.session):
        return redirect(_safe_next(request.GET.get('next')))
    if request.method == 'POST':
        try:
            acct.login(request.session, request.POST.get('email', '').strip(), request.POST.get('password', ''))
            messages.success(request, 'Willkommen zurück!')
            return redirect(_safe_next(request.POST.get('next')))
        except acct.AdvertiserError as e:
            messages.error(request, e.message)
    return _render(request, 'login.html', next=request.GET.get('next', ''), email=request.POST.get('email', ''))


def register_view(request):
    if acct.current(request.session):
        return redirect('werbekonto')
    form = {k: request.POST.get(k, '').strip() for k in ('company_name', 'contact_name', 'phone', 'email')}
    if request.method == 'POST':
        password = request.POST.get('password', '')
        errors = []
        if len(form['company_name']) < 2:
            errors.append('Bitte die Firma angeben.')
        if len(password) < 8:
            errors.append('Das Passwort muss mindestens 8 Zeichen haben.')
        if password != request.POST.get('password2', ''):
            errors.append('Die Passwörter stimmen nicht überein.')
        if not request.POST.get('terms'):
            errors.append('Bitte die Hinweise zur Prüfung und zu den Rechten bestätigen.')
        if not errors:
            try:
                logged_in = acct.signup(request.session, form['email'], password, form['company_name'], form['contact_name'],
                                        form['phone'], redirect_to=request.build_absolute_uri('/werbung/konto/login/'))
                if logged_in:
                    messages.success(request, 'Werbekonto angelegt – willkommen!')
                    return redirect('werbekonto')
                return _render(request, 'confirm.html', email=form['email'])
            except acct.AdvertiserError as e:
                errors.append(e.message)
        for err in errors:
            messages.error(request, err)
    return _render(request, 'register.html', form=form)


def logout_view(request):
    acct.logout(request.session)
    messages.info(request, 'Abgemeldet.')
    return redirect('werbung')


def activate_view(request):
    konto = acct.current(request.session)
    if not konto:
        return redirect('werbekonto_login')
    if request.method == 'POST':
        company = request.POST.get('company_name', '').strip()
        if len(company) < 2:
            messages.error(request, 'Bitte die Firma angeben.')
        else:
            try:
                acct.claim_account(konto, company)
                messages.success(request, 'Werbekonto aktiviert.')
                return redirect('werbekonto')
            except acct.AdvertiserError as e:
                messages.error(request, e.message)
    return _render(request, 'activate.html')


@advertiser_required
def dashboard(request):
    konto = request.werbekonto
    bookings, profile, error = [], {}, None
    try:
        profile = acct.profile(konto)
        bookings = acct.my_bookings(konto)
    except acct.AdvertiserError as e:
        error = e.message
    for b in bookings:
        b['status_label'], b['status_color'] = STATUS.get(b.get('status'), (b.get('status'), 'secondary'))
        if b.get('status') == 'approved' and b.get('spot_active') is False:
            b['status_label'], b['status_color'] = 'Pausiert', 'secondary'
        b['price_eur'] = b['price_cents'] / 100 if b.get('price_cents') is not None else None
        b['start'] = _parse_date(b.get('start_date'))
        b['end'] = _parse_date(b.get('end_date'))
    show = request.GET.get('statistik')
    stats = None
    if show and any(b['id'] == show and b.get('spot_id') for b in bookings):
        try:
            stats = acct.booking_stats(konto, show)
            peak = max([d['plays'] for d in stats.get('by_day', [])] or [1])
            for d in stats.get('by_day', []):
                d['pct'] = round(d['plays'] / peak * 100)
                d['date'] = _parse_date(d['day'])
        except acct.AdvertiserError as e:
            messages.error(request, e.message)
    counts = {
        'total': len(bookings),
        'pending': sum(1 for b in bookings if b.get('status') == 'pending'),
        'approved': sum(1 for b in bookings if b.get('status') == 'approved'),
    }
    return _render(request, 'dashboard.html', bookings=bookings, profile=profile, error=error,
                   counts=counts, stats=stats, stats_for=show)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@advertiser_required
def new_booking(request):
    konto = request.werbekonto
    try:
        profile = acct.profile(konto)
    except acct.AdvertiserError:
        profile = {}
    today = date.today()
    defaults = {
        'company_name': profile.get('company_name', ''), 'contact_name': profile.get('contact_name') or '',
        'contact_email': konto.get('email') or '', 'contact_phone': profile.get('phone') or '',
        'ad_title': '', 'ad_description': '', 'spot_video_url': '', 'spot_duration_seconds': '20',
        'start_date': (today + timedelta(days=3)).isoformat(), 'end_date': (today + timedelta(days=30)).isoformat(),
        'desired_slot': 'Ganztägig', 'plays_per_day': '4', 'budget_eur': '',
    }
    form = {k: request.POST.get(k, v) for k, v in defaults.items()} if request.method == 'POST' else defaults
    targets = request.POST.getlist('target_regions') if request.method == 'POST' else []

    if request.method == 'POST':
        errors = []
        video = request.FILES.get('spot_file')
        if video:
            info = acct.inspect_mp4(video)
            errors += acct.creative_errors(info, video.size)
            if not errors:
                try:
                    form['spot_video_url'] = acct.upload_spot(konto, video)
                    if info['duration']:
                        form['spot_duration_seconds'] = str(round(info['duration']))
                except acct.AdvertiserError as e:
                    errors.append(f"Upload fehlgeschlagen: {e.message}")
        if not form['spot_video_url'].startswith('https://'):
            errors.append('Bitte eine Spot-Datei hochladen oder einen Link (https://…) angeben.')
        if not request.POST.get('consent'):
            errors.append('Bitte der Datenverarbeitung zustimmen.')
        if not errors:
            labels = dict(acct.REGION_CHOICES)
            valid_targets = [t for t in targets if t in labels]
            payload = {
                'company_name': form['company_name'], 'contact_name': form['contact_name'],
                'contact_email': form['contact_email'], 'contact_phone': form['contact_phone'],
                'ad_title': form['ad_title'], 'ad_description': form['ad_description'],
                'spot_video_url': form['spot_video_url'], 'spot_duration_seconds': _int(form['spot_duration_seconds'], 30),
                'start_date': form['start_date'], 'end_date': form['end_date'],
                'desired_slot': form['desired_slot'] if form['desired_slot'] in acct.SLOTS else 'Ganztägig',
                'plays_per_day': _int(form['plays_per_day'], 4), 'consent': True,
                'budget_eur': float(form['budget_eur'].replace(',', '.')) if form['budget_eur'].strip() else None,
                'target_regions': valid_targets, 'target_labels': [labels[t] for t in valid_targets],
                'is_premium': bool(request.POST.get('is_premium')) and not valid_targets,
            }
            try:
                result = acct.create_booking(konto, payload)
                price = result.get('price_eur')
                messages.success(request, 'Buchung eingereicht' + (f' – Richtpreis {price:.2f} €'.replace('.', ',') if isinstance(price, (int, float)) else '')
                                 + '. Wir prüfen den Spot und geben ihn frei.')
                return redirect('werbekonto')
            except acct.AdvertiserError as e:
                errors.append(e.message)
        for err in errors:
            messages.error(request, err)
    return _render(request, 'booking_form.html', form=form, targets=targets,
                   regions=acct.REGION_CHOICES, slots=acct.SLOTS, min_date=today.isoformat())


def _int(value, default):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@advertiser_required
@require_POST
def pause(request, booking_id):
    try:
        acct.set_paused(request.werbekonto, booking_id, request.POST.get('paused') == '1')
        messages.success(request, 'Spot pausiert.' if request.POST.get('paused') == '1' else 'Spot läuft wieder.')
    except acct.AdvertiserError as e:
        messages.error(request, e.message)
    return redirect('werbekonto')


@advertiser_required
@require_POST
def withdraw(request, booking_id):
    try:
        acct.withdraw(request.werbekonto, booking_id)
        messages.success(request, 'Anfrage zurückgezogen.')
    except acct.AdvertiserError as e:
        messages.error(request, e.message)
    return redirect('werbekonto')
