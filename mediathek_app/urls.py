"""
RSL Mediathek - URLs
"""
from django.urls import path
from . import views

app_name = 'mediathek'

urlpatterns = [
    # Home
    path('', views.mediathek_home, name='home'),
    
    # Videos
    path('videos/', views.video_list, name='video_list'),
    path('videos/<slug:slug>/', views.video_player, name='video_player'),
    
    # Serien
    path('serien/', views.series_list, name='series_list'),
    path('serien/<slug:slug>/', views.series_detail, name='series_detail'),
    path('serien/<slug:series_slug>/staffel-<int:season_number>/', 
         views.season_detail, name='season_detail'),
    path('serien/<slug:series_slug>/staffel-<int:season_number>/episode-<int:episode_number>/',
         views.episode_player, name='episode_player'),
    
    # Live
    path('live/', views.live_overview, name='live_overview'),
    path('live/<slug:slug>/', views.live_player, name='live_player'),
    
    # Playlists
    path('playlists/', views.playlist_list, name='playlist_list'),
    path('playlists/<slug:slug>/', views.playlist_detail, name='playlist_detail'),
    
    # Kategorie
    path('kategorie/<slug:slug>/', views.category_detail, name='category_detail'),
    
    # Suche
    path('suche/', views.search, name='search'),
    
    # API
    path('api/videos/', views.api_videos, name='api_videos'),
    path('api/series/', views.api_series, name='api_series'),
    path('api/live/', views.api_live, name='api_live'),
]
