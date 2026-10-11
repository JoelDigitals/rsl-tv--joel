from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "RSL TV – Joel Digitals"
admin.site.site_title = "RSL TV Admin"
admin.site.index_title = "Senderverwaltung"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tv.urls')),
    path('mediathek/', include('mediathek.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
