from django.apps import AppConfig

class MediathekConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mediathek_app'   # ✅ DAS ist der Fix
    verbose_name = 'RSL Mediathek'