from django.db import migrations

# Quellen, die das RSL-System bereits nutzt (laut Nachrichten-Ausgaben und Programm).
# Im Admin unter „Quellen“ frei bearbeitbar.
STARTDATEN = [
    {
        'name': 'tagesschau.de',
        'kategorie': 'nachrichten',
        'url': 'https://www.tagesschau.de/',
        'beschreibung': 'Grundlage für Meldungen in den RSL Nachrichten. Der jeweilige Originalartikel ist bei jeder Meldung verlinkt.',
        'reihenfolge': 10,
    },
    {
        'name': 'Open-Meteo',
        'kategorie': 'daten',
        'url': 'https://open-meteo.com/',
        'beschreibung': 'Wetterdaten für den Wetterbericht in den RSL Nachrichten.',
        'lizenz': 'CC BY 4.0',
        'reihenfolge': 10,
    },
    {
        'name': 'YouTube',
        'kategorie': 'video',
        'url': 'https://www.youtube.com/',
        'beschreibung': 'Viele Sendungen im Programm und in der Mediathek werden über YouTube eingebunden. Rechte und Urheberschaft liegen bei den jeweiligen Kanälen.',
        'reihenfolge': 10,
    },
]


def anlegen(apps, schema_editor):
    Quelle = apps.get_model('tv', 'Quelle')
    for daten in STARTDATEN:
        Quelle.objects.get_or_create(name=daten['name'], defaults=daten)


def entfernen(apps, schema_editor):
    Quelle = apps.get_model('tv', 'Quelle')
    Quelle.objects.filter(name__in=[d['name'] for d in STARTDATEN]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tv', '0009_quelle'),
    ]

    operations = [
        migrations.RunPython(anlegen, entfernen),
    ]
