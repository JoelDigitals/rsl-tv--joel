from django.core.management.base import BaseCommand

from mediathek import archive


class Command(BaseCommand):
    help = "Speichert neue Sendungen und Live-Streams aus der RSL Broadcast-API in der Mediathek."

    def handle(self, *args, **options):
        new_items, new_live, ended = archive.sync(force=True)
        self.stdout.write(self.style.SUCCESS(
            f"Mediathek synchronisiert: {new_items} neue Sendungen, "
            f"{new_live} neue Live-Streams, {ended} Live-Streams beendet."
        ))
