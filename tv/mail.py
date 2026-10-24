"""
RSL TV – Mailjet E-Mail Hilfsfunktionen
Joel Digitals
"""
import logging
from django.conf import settings

log = logging.getLogger('RSL.mail')


def send_mailjet(to_email, to_name, subject, html_content, text_content=''):
    """
    Sendet eine E-Mail über Mailjet.
    Gibt True bei Erfolg zurück, False bei Fehler.
    """
    api_key = settings.MAILJET_API_KEY
    secret = settings.MAILJET_SECRET_KEY

    if not api_key or not secret:
        log.warning("Mailjet nicht konfiguriert – E-Mail wird nicht gesendet.")
        return False

    try:
        from mailjet_rest import Client
        mj = Client(auth=(api_key, secret), version='v3.1')

        data = {
            'Messages': [
                {
                    'From': {
                        'Email': settings.DEFAULT_FROM_EMAIL,
                        'Name': settings.DEFAULT_FROM_NAME,
                    },
                    'To': [{'Email': to_email, 'Name': to_name}],
                    'Subject': subject,
                    'TextPart': text_content or subject,
                    'HTMLPart': html_content,
                }
            ]
        }

        result = mj.send.create(data=data)
        if result.status_code == 200:
            log.info(f"E-Mail gesendet an {to_email}")
            return True
        else:
            log.error(f"Mailjet Fehler {result.status_code}: {result.json()}")
            return False

    except Exception as e:
        log.error(f"Mailjet Exception: {e}")
        return False


def send_booking_confirmation(booking):
    """Sendet Buchungsbestätigung an Kunden"""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a0f;color:#e8e8f0;padding:30px;border-radius:8px;">
        <div style="text-align:center;margin-bottom:30px;">
            <h1 style="font-size:3rem;color:#e63946;letter-spacing:6px;margin:0;">RSL</h1>
            <p style="color:#888;margin:5px 0 0;letter-spacing:3px;font-size:0.85rem;text-transform:uppercase;">von Joel Digitals</p>
        </div>

        <h2 style="color:#e63946;border-bottom:2px solid #e63946;padding-bottom:10px;">Buchungsbestätigung</h2>

        <p>Sehr geehrte/r {booking.customer_name},</p>
        <p>vielen Dank für Ihre Buchungsanfrage bei RSL! Wir haben Ihre Anfrage erhalten und prüfen diese innerhalb von 24 Stunden.</p>

        <div style="background:#1a1a2e;padding:20px;border-radius:6px;margin:20px 0;border-left:4px solid #e63946;">
            <h3 style="margin-top:0;color:#e63946;">Ihre Buchungsdetails</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:6px 0;color:#888;">Buchungsnummer:</td><td style="padding:6px 0;font-weight:bold;">{booking.id}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">Paket:</td><td style="padding:6px 0;">{booking.get_package_display()}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">Unternehmen:</td><td style="padding:6px 0;">{booking.company_name}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">Zeitraum:</td><td style="padding:6px 0;">{booking.start_date.strftime('%d.%m.%Y')} – {booking.end_date.strftime('%d.%m.%Y')}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">Betrag:</td><td style="padding:6px 0;color:#e63946;font-weight:bold;font-size:1.2rem;">{booking.price} €</td></tr>
            </table>
        </div>

        <div style="background:#1a1a2e;padding:20px;border-radius:6px;margin:20px 0;border-left:4px solid #f4a261;">
            <h3 style="margin-top:0;color:#f4a261;">📋 Nächste Schritte</h3>
            <ol style="padding-left:20px;line-height:1.8;">
                <li>Wir prüfen Ihre Buchung (innerhalb 24 Stunden)</li>
                <li>Sie erhalten eine <strong>Rechnung</strong> per E-Mail</li>
                <li>Nach Zahlungseingang wird Ihr Werbspot freigeschaltet</li>
                <li>Ihr Spot läuft automatisch auf RSL 📺</li>
            </ol>
        </div>

        <p style="color:#888;font-size:0.85rem;">Bei Fragen wenden Sie sich bitte an: <a href="mailto:{settings.DEFAULT_FROM_EMAIL}" style="color:#e63946;">{settings.DEFAULT_FROM_EMAIL}</a></p>

        <div style="text-align:center;margin-top:30px;padding-top:20px;border-top:1px solid #2d2d44;">
            <p style="color:#555;font-size:0.8rem;">RSL TV – Dein Sender. Deine Welt.<br>Ein Sender von Joel Digitals</p>
        </div>
    </div>
    """
    return send_mailjet(
        booking.email, booking.customer_name,
        f'RSL – Buchungsbestätigung #{booking.id}', html
    )


def send_invoice(booking):
    """Sendet Rechnung an Kunden"""
    import datetime
    invoice_num = f"RSL-{datetime.date.today().year}-{str(booking.id).zfill(4)}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;background:#fff;color:#333;padding:40px;">

        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:40px;">
            <div>
                <h1 style="font-size:3rem;color:#e63946;letter-spacing:6px;margin:0;">RSL</h1>
                <p style="color:#888;margin:2px 0 0;letter-spacing:2px;font-size:0.8rem;">VON JOEL DIGITALS</p>
            </div>
            <div style="text-align:right;">
                <h2 style="margin:0;color:#e63946;">RECHNUNG</h2>
                <p style="margin:5px 0 0;color:#666;">Nr. {invoice_num}</p>
                <p style="margin:2px 0 0;color:#666;font-size:0.9rem;">{datetime.date.today().strftime('%d.%m.%Y')}</p>
            </div>
        </div>

        <div style="background:#f9f9f9;padding:20px;border-radius:6px;margin-bottom:30px;">
            <h4 style="margin:0 0 10px;color:#333;">Rechnungsempfänger</h4>
            <p style="margin:0;">{booking.company_name}<br>{booking.customer_name}<br>{booking.email}</p>
        </div>

        <table style="width:100%;border-collapse:collapse;margin-bottom:30px;">
            <thead>
                <tr style="background:#e63946;color:white;">
                    <th style="padding:12px;text-align:left;">Beschreibung</th>
                    <th style="padding:12px;text-align:right;">Betrag</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid #eee;">
                    <td style="padding:12px;">
                        <strong>RSL Werbepaket: {booking.get_package_display()}</strong><br>
                        <small style="color:#666;">Zeitraum: {booking.start_date.strftime('%d.%m.%Y')} – {booking.end_date.strftime('%d.%m.%Y')}</small><br>
                        <small style="color:#666;">Zeitslot: {booking.get_timeslot_display()}</small>
                    </td>
                    <td style="padding:12px;text-align:right;font-weight:bold;">{booking.price_net:.2f} €</td>
                </tr>
                <tr style="border-bottom:1px solid #eee;">
                    <td style="padding:12px;color:#666;">MwSt. 19%</td>
                    <td style="padding:12px;text-align:right;color:#666;">{booking.price_vat:.2f} €</td>
                </tr>
                <tr style="background:#f0f0f0;">
                    <td style="padding:12px;font-weight:bold;font-size:1.1rem;">Gesamtbetrag</td>
                    <td style="padding:12px;text-align:right;font-weight:bold;font-size:1.2rem;color:#e63946;">{booking.price:.2f} €</td>
                </tr>
            </tbody>
        </table>

        <div style="background:#fff3cd;border:1px solid #ffc107;padding:20px;border-radius:6px;margin-bottom:30px;">
            <h4 style="margin:0 0 10px;color:#856404;">💳 Zahlungsinformationen</h4>
            <p style="margin:0;line-height:1.8;">
                <strong>Kontoinhaber:</strong> Joel Digitals<br>
                <strong>IBAN:</strong> DE__ ____ ____ ____ __ (bitte in .env eintragen)<br>
                <strong>BIC:</strong> XXXXXXXX<br>
                <strong>Verwendungszweck:</strong> {invoice_num}<br>
                <strong>Zahlungsziel:</strong> 14 Tage nach Rechnungseingang
            </p>
        </div>

        <p style="color:#888;font-size:0.85rem;">Nach Zahlungseingang wird Ihr Werbspot innerhalb von 24 Stunden auf RSL freigeschaltet.<br>
        Bei Fragen: <a href="mailto:{settings.DEFAULT_FROM_EMAIL}" style="color:#e63946;">{settings.DEFAULT_FROM_EMAIL}</a></p>

        <div style="text-align:center;margin-top:30px;padding-top:20px;border-top:1px solid #eee;color:#aaa;font-size:0.8rem;">
            RSL TV – Joel Digitals | Steuernummer: [Ihre StNr] | USt-IdNr.: [Ihre USt-IdNr]
        </div>
    </div>
    """
    return send_mailjet(
        booking.email, booking.customer_name,
        f'RSL – Rechnung {invoice_num}', html
    )


def send_booking_approved(booking):
    """Benachrichtigung: Spot freigeschaltet"""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a0f;color:#e8e8f0;padding:30px;border-radius:8px;">
        <h1 style="font-size:3rem;color:#e63946;letter-spacing:6px;text-align:center;">RSL</h1>
        <h2 style="color:#28a745;">✅ Ihr Werbspot ist jetzt live!</h2>
        <p>Sehr geehrte/r {booking.customer_name},</p>
        <p>Ihre Zahlung wurde verbucht und Ihr Werbspot wurde soeben auf RSL freigeschaltet.</p>
        <div style="background:#1a1a2e;padding:20px;border-radius:6px;border-left:4px solid #28a745;">
            <p><strong>Paket:</strong> {booking.get_package_display()}</p>
            <p><strong>Zeitraum:</strong> {booking.start_date.strftime('%d.%m.%Y')} – {booking.end_date.strftime('%d.%m.%Y')}</p>
            <p style="margin:0;"><strong>Ihr Spot läuft ab sofort auf RSL! 📺</strong></p>
        </div>
        <p style="color:#888;font-size:0.85rem;margin-top:20px;">RSL TV – Joel Digitals</p>
    </div>
    """
    return send_mailjet(
        booking.email, booking.customer_name,
        'RSL – Ihr Werbspot ist jetzt live! 🎉', html
    )


def send_new_booking_admin(booking):
    """Interne Benachrichtigung: neue Buchungsanfrage"""
    html = f"""
    <div style="font-family:Arial,sans-serif;padding:20px;">
        <h2 style="color:#e63946;">🔔 Neue Werbebuchung eingegangen!</h2>
        <table style="border-collapse:collapse;width:100%;">
            <tr><td style="padding:8px;font-weight:bold;">Buchungs-ID:</td><td style="padding:8px;">{booking.id}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Kunde:</td><td style="padding:8px;">{booking.customer_name}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Unternehmen:</td><td style="padding:8px;">{booking.company_name}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">E-Mail:</td><td style="padding:8px;">{booking.email}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Paket:</td><td style="padding:8px;">{booking.get_package_display()}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Zeitraum:</td><td style="padding:8px;">{booking.start_date} – {booking.end_date}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Betrag:</td><td style="padding:8px;color:#e63946;font-weight:bold;">{booking.price} €</td></tr>
            <tr><td style="padding:8px;font-weight:bold;">Video-URL:</td><td style="padding:8px;"><a href="{booking.video_url}">{booking.video_url}</a></td></tr>
        </table>
        <p><a href="{settings.SITE_URL}/admin/tv/adbooking/{booking.id}/change/" style="background:#e63946;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">Im Admin öffnen</a></p>
    </div>
    """
    return send_mailjet(
        settings.ADMIN_EMAIL, 'RSL Admin',
        f'Neue Buchung: {booking.company_name} – {booking.get_package_display()}', html
    )
