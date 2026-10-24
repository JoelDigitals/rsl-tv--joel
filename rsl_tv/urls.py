from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rsl_tv.broadcast_api import broadcast_api_proxy

admin.site.site_header = "RSL TV – Joel Digitals"
admin.site.site_title = "RSL TV Admin"
admin.site.index_title = "Senderverwaltung"

urlpatterns = [
    path('admin/', admin.site.urls),
    # Broadcast-API unter der eigenen Domain (Serien, Mediathek, Programm, News)
    path('api/broadcast-api/', broadcast_api_proxy, name='broadcast_api'),
    path('functions/v1/broadcast-api/', broadcast_api_proxy, name='broadcast_api_alt'),
    path('', include('tv.urls')),
    path('mediathek/', include('mediathek.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
