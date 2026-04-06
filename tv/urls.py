from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('programm/', views.program, name='program'),
    path('live/', views.live, name='live'),
    path('mediathek/', views.mediathek, name='mediathek'),
    path('ueber-uns/', views.ueber_uns, name='ueber_uns'),
    path('kontakt/', views.kontakt, name='kontakt'),
    path('impressum/', views.impressum, name='impressum'),
    path('datenschutz/', views.datenschutz, name='datenschutz'),
    path('werbung/', views.werbung, name='werbung'),
    path('werbung/buchen/', views.werbung_buchen, name='werbung_buchen'),
    path('werbung/buchen/<str:package>/', views.werbung_buchen, name='werbung_buchen_package'),
    path('werbung/erfolg/', views.werbung_success, name='werbung_success'),
    # API
    path('api/playlist/', views.api_playlist, name='api_playlist'),
    path('api/current/', views.api_current_show, name='api_current'),
    path('api/news/', views.api_news, name='api_news'),
    path('api/logo/', views.api_logo, name='api_logo'),
    # Live Admin (AJAX)
    path('api/live/<int:stream_id>/start-ad/', views.live_start_ad, name='live_start_ad'),
    path('api/live/<int:stream_id>/stop-ad/', views.live_stop_ad, name='live_stop_ad'),
    # TV Admin / Regie
    path('tv-admin/', views.tv_admin_dashboard, name='tv_admin_dashboard'),
    path('tv-admin/select-camera/<int:stream_id>/<int:camera_id>/', views.tv_admin_select_camera, name='tv_admin_select_camera'),
    path('tv-admin/room/<int:room_id>/', views.director_room_dashboard, name='director_room_dashboard'),
    path('tv-admin/room/<int:room_id>/start-stream/', views.start_stream_to_platform, name='start_stream_to_platform'),
    path('tv-admin/room/<int:room_id>/stop-stream/', views.stop_stream_from_platform, name='stop_stream_from_platform'),
    path('tv-admin/room/<int:room_id>/go-live/', views.go_live_override, name='go_live_override'),
    path('tv-admin/room/<int:room_id>/cut-out/', views.cut_out, name='cut_out'),
    path('tv-admin/room/<int:room_id>/standby/', views.show_standby_image, name='show_standby_image'),
    # IPTV
    path('iptv/rsl.m3u', views.iptv_playlist, name='iptv_playlist'),
]