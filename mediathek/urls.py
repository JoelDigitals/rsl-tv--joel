from django.urls import path
from . import views

app_name = 'mediathek'

urlpatterns = [
    # PUBLIC PAGES
    path('', views.home, name='home'),
    path('videos/', views.video_list, name='video_list'),
    path('videos/<slug:slug>/', views.video_player, name='video_player'),
    
    path('serien/', views.series_list, name='series_list'),
    path('serien/<slug:slug>/', views.series_detail, name='series_detail'),
    path('serien/<slug:series_slug>/staffel-<int:season_number>/', views.season_detail, name='season_detail'),
    path('serien/<slug:series_slug>/staffel-<int:season_number>/episode-<int:episode_number>/', views.episode_player, name='episode_player'),
    
    path('live/', views.live_overview, name='live_overview'),
    path('live/streams/', views.live_recordings, name='live_recordings'),
    path('live/streams/<int:pk>/', views.live_recording_player, name='live_recording_player'),
    path('live/<slug:slug>/', views.live_player, name='live_player'),
    path('programm/', views.schedule, name='schedule'),
    
    path('playlists/', views.playlist_list, name='playlist_list'),
    path('playlists/<slug:slug>/', views.playlist_detail, name='playlist_detail'),
    
    path('kategorie/<slug:slug>/', views.category_detail, name='category_detail'),
    path('rubrik/<slug:slug>/', views.api_category, name='api_category'),
    path('suche/', views.search, name='search'),

    # INHALTE AUS DER RSL BROADCAST-API
    path('reihe/<slug:slug>/', views.api_series_detail, name='api_series_detail'),
    path('sendung/<uuid:program_id>/', views.program_player, name='program_player'),
    path('sendungen/', views.library_list, name='library_list'),
    path('ausgabe/<uuid:item_id>/', views.library_player, name='library_player'),
    path('nachrichten/', views.news_list, name='news_list'),
    path('nachrichten/<uuid:edition_id>/', views.edition_detail, name='edition_detail'),
    path('studio/<uuid:studio_id>/', views.studio_player, name='studio_player'),

    # API ENDPOINTS
    path('api/viewer-heartbeat/', views.api_viewer_heartbeat, name='api_viewer_heartbeat'),
    path('api/viewer-count/<slug:stream_slug>/', views.api_viewer_count, name='api_viewer_count'),
    path('api/chat-send/', views.api_chat_send, name='api_chat_send'),
    path('api/chat-messages/<slug:stream_slug>/', views.api_chat_messages, name='api_chat_messages'),
    path('api/ads/<str:content_type>/<int:content_id>/', views.api_get_ads, name='api_get_ads'),
    path('api/ad-click/', views.api_ad_click, name='api_ad_click'),
    
    # CUSTOM ADMIN (erreichbar unter /mediathek/admin/)
    path('admin/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('admin/videos/', views.custom_admin_videos, name='custom_admin_videos'),
    path('admin/videos/neu/', views.custom_admin_video_edit, name='custom_admin_video_edit'),
    path('admin/videos/<int:video_id>/bearbeiten/', views.custom_admin_video_edit, name='custom_admin_video_edit'),
    path('admin/playlists/', views.custom_admin_playlists, name='custom_admin_playlists'),
    path('admin/playlists/neu/', views.custom_admin_playlist_edit, name='custom_admin_playlist_edit'),
    path('admin/playlists/<int:playlist_id>/bearbeiten/', views.custom_admin_playlist_edit, name='custom_admin_playlist_edit'),
    path('admin/playlists/<int:playlist_id>/youtube-import/', views.custom_admin_youtube_import, name='custom_admin_youtube_import'),
    path('admin/youtube-debugger/', views.custom_admin_youtube_debug, name='custom_admin_youtube_debug'),
    path('admin/serien/', views.custom_admin_series, name='custom_admin_series'),
    path('admin/livestreams/', views.custom_admin_livestreams, name='custom_admin_livestreams'),
]
