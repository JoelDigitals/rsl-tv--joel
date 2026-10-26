import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rsl_tv.settings')
application = get_wsgi_application()

logger = logging.getLogger(__name__)

# Fehlende Datenbank-Migrationen beim Start automatisch ausführen.
# Render (Free-Plan) hat weder Shell noch Pre-Deploy-Befehl – ohne diesen Schritt
# fehlen neue Tabellen (z. B. tv_quelle, mediathek_archivedbroadcast).
# Abschalten mit AUTO_MIGRATE=0.
if os.environ.get('AUTO_MIGRATE', '1') != '0':
    def _auto_migrate():
        from django.core.management import call_command
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        if not executor.migration_plan(executor.loader.graph.leaf_nodes()):
            return  # alles aktuell

        # Mehrere Gunicorn-Worker starten gleichzeitig: Postgres-Sperre,
        # damit nur einer migriert und die anderen warten.
        is_pg = connection.vendor == 'postgresql'
        if is_pg:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_lock(%s)', [81726354])
        try:
            call_command('migrate', interactive=False, verbosity=1)
            from django.core.cache import cache
            cache.delete('mediathek:archive:available')
        finally:
            if is_pg:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_unlock(%s)', [81726354])

    try:
        _auto_migrate()
    except Exception:
        logger.exception("Automatische Migration fehlgeschlagen – bitte 'python manage.py migrate' ausführen.")
