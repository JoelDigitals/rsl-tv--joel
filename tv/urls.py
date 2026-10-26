"""
RSL TV – URLs (vereinigt)
"""
from django.urls import path
from . import views
from . import upload_views  # NEU: Upload Views
from .upload_center_view import upload_center  # NEU: Upload Center

urlpatterns = [
    # ══════════════════════════════════════════════════════════════════════════
    # ÖFFENTLICHE SEITEN
    # ══════════════════════════════════════════════════════════════════════════
    path('', views.index, name='home'),
    path('programm/', views.program, name='program'),
    path('live/', views.live, name='live'),
    path('mediathek-1/', views.mediathek, name='mediathek'),
    path('mediathek-1/video/<int:video_id>/', views.video_player, name='video_player'),
    path('ueber-uns/', views.ueber_uns, name='ueber_uns'),
    path('kontakt/', views.kontakt, name='kontakt'),
    path('impressum/', views.impressum, name='impressum'),
    path('datenschutz/', views.datenschutz, name='datenschutz'),
    path('quellen/', views.quellen, name='quellen'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # FILE UPLOADS (NEU - JDS Cloud Integration)
    # ══════════════════════════════════════════════════════════════════════════
    path('upload/', upload_center, name='upload_center'),  # Upload Dashboard
    path('upload/video/', upload_views.upload_video, name='upload_video'),
    path('upload/video/ajax/', upload_views.upload_video_ajax, name='upload_video_ajax'),
    path('upload/thumbnail/', upload_views.upload_thumbnail, name='upload_thumbnail'),
    path('upload/ad-video/', upload_views.upload_ad_video, name='upload_ad_video'),
    path('upload/logo/', upload_views.upload_logo, name='upload_logo'),
    path('upload/livestream/', upload_views.upload_live_stream, name='upload_live_stream'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # WERBUNG
    # ══════════════════════════════════════════════════════════════════════════
    path('werbung/', views.werbung, name='werbung'),
    path('werbung/buchen/', views.werbung_buchen, name='werbung_buchen'),
    path('werbung/buchen/<str:package>/', views.werbung_buchen, name='werbung_buchen_package'),
    path('werbung/erfolg/', views.werbung_success, name='werbung_success'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # API ENDPUNKTE (JSON für FFmpeg & Frontend)
    # ══════════════════════════════════════════════════════════════════════════
    path('api/playlist/', views.api_playlist, name='api_playlist'),
    path('api/current/', views.api_current_show, name='api_current'),
    path('api/jetzt/', views.api_now_next, name='api_now_next'),
    path('api/current-show/', views.api_current_show_extended, name='api_current_show_extended'),
    path('api/news/', views.api_news, name='api_news'),
    path('api/logo/', views.api_logo, name='api_logo'),
    path('api/standby/', views.api_standby_image, name='api_standby'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # TV-Display APIs (Werbepausen)
    # ══════════════════════════════════════════════════════════════════════════
    path('api/ad-break-status/', views.api_ad_break_status, name='api_ad_break_status'),
    path('api/ad-break/start/', views.api_start_ad_break, name='api_start_ad_break'),
    path('api/ad-break/end/', views.api_end_ad_break, name='api_end_ad_break'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # LIVE ADMIN (AJAX)
    # ══════════════════════════════════════════════════════════════════════════
    path('api/live/<int:stream_id>/start-ad/', views.live_start_ad, name='live_start_ad'),
    path('api/live/<int:stream_id>/stop-ad/', views.live_stop_ad, name='live_stop_ad'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # TV ADMIN / REGIE PANEL (Legacy)
    # ══════════════════════════════════════════════════════════════════════════
    path('tv-admin/', views.tv_admin_dashboard, name='tv_admin_dashboard'),
    path('tv-admin/select-camera/<int:stream_id>/<int:camera_id>/', views.tv_admin_select_camera, name='tv_admin_select_camera'),
    path('tv-admin/room/<int:room_id>/', views.director_room_dashboard, name='director_room_dashboard'),
    path('tv-admin/room/<int:room_id>/start-stream/', views.start_stream_to_platform, name='start_stream_to_platform'),
    path('tv-admin/room/<int:room_id>/stop-stream/', views.stop_stream_from_platform, name='stop_stream_from_platform'),
    path('tv-admin/room/<int:room_id>/go-live/', views.go_live_override, name='go_live_override'),
    path('tv-admin/room/<int:room_id>/cut-out/', views.cut_out, name='cut_out'),
    path('tv-admin/room/<int:room_id>/standby/', views.show_standby_image, name='show_standby_image'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # IPTV
    # ══════════════════════════════════════════════════════════════════════════
    path('iptv/rsl.m3u', views.iptv_playlist, name='iptv_playlist'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # PROGRAMM-REGIERAUM (24/7 Streaming)
    # ══════════════════════════════════════════════════════════════════════════
    path('tv-admin/programm/', views.program_room_dashboard, name='program_room_dashboard'),
    path('tv-admin/programm/start/', views.program_room_start_stream, name='program_room_start'),
    path('tv-admin/programm/stop/', views.program_room_stop_stream, name='program_room_stop'),
    path('tv-admin/programm/werbung/', views.program_room_trigger_ad, name='program_room_trigger_ad'),
    path('tv-admin/programm/keys/', views.program_room_save_keys, name='program_room_save_keys'),
    path('tv-admin/programm/status/', views.program_room_status_api, name='program_room_status'),
    path('tv-admin/programm/download/', views.program_room_download_video, name='program_room_download'),
    path('tv-admin/programm/clear-log/', views.program_clear_log, name='program_clear_log'),
    path('tv-admin/programm/get-log/', views.program_get_log, name='program_get_log'),
    
    # Kurz-URLs
    path('program/', views.program_room_dashboard, name='program_room'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # ERWEITERTER REGIERAUM
    # ══════════════════════════════════════════════════════════════════════════
    path('regie/', views.director_room_view, name='director_room'),
    path('regie/start-stream/', views.director_start_stream, name='director_start_stream'),
    path('regie/stop-stream/', views.director_stop_stream, name='director_stop_stream'),
    path('regie/switch-camera/', views.director_switch_camera, name='director_switch_camera'),
    path('regie/camera-preview/<int:room_id>/<int:camera_id>/', views.director_camera_preview, name='director_camera_preview'),
    path('regie/set-preview/', views.director_set_preview, name='director_set_preview'),
    path('regie/toggle-audio/', views.director_toggle_audio, name='director_toggle_audio'),
    path('regie/set-audio-volume/', views.director_set_audio_volume, name='director_set_audio_volume'),
    path('regie/stream-log/', views.director_stream_log, name='director_stream_log'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # REPLAY STUDIO
    # ══════════════════════════════════════════════════════════════════════════
    path('replay/', views.replay_studio_view, name='replay_studio'),
    path('replay/create-clip/', views.replay_create_clip, name='replay_create_clip'),
    path('replay/play-clip/', views.replay_play_clip, name='replay_play_clip'),
    path('replay/toggle-favorite/', views.replay_toggle_favorite, name='replay_toggle_favorite'),
    path('replay/delete-clip/', views.replay_delete_clip, name='replay_delete_clip'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # RUNDOWN-PLANUNG
    # ══════════════════════════════════════════════════════════════════════════
    path('rundown/', views.rundown_planner_view, name='rundown_planner'),
    path('rundown/<int:rundown_id>/', views.rundown_detail_view, name='rundown_detail'),
    path('rundown/create/', views.rundown_create, name='rundown_create'),
    path('rundown/add-segment/', views.rundown_add_segment, name='rundown_add_segment'),
    path('rundown/reorder-segments/', views.rundown_reorder_segments, name='rundown_reorder_segments'),
    path('rundown/start/', views.rundown_start, name='rundown_start'),
    path('rundown/stop/', views.rundown_stop, name='rundown_stop'),
    path('rundown/next-segment/', views.rundown_next_segment, name='rundown_next_segment'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # SZENEN-VERWALTUNG
    # ══════════════════════════════════════════════════════════════════════════
    path('szenen/', views.scenes_view, name='scenes'),
    path('szenen/activate/', views.scene_activate, name='scene_activate'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # LIVE STUDIO (OBS-Style)
    # ══════════════════════════════════════════════════════════════════════════
    path('live-studio/', views.live_studio, name='live_studio'),
    path('api/cameras/', views.api_cameras_list, name='api_cameras_list'),
    path('api/scenes/', views.api_scenes_list, name='api_scenes_list'),
    path('api/rundown/active/', views.api_rundown_active, name='api_rundown_active'),
    path('api/ads/get-break/', views.api_get_ad_break, name='api_get_ad_break'),
    path('api/stream/key/<str:platform>/', views.api_stream_key, name='api_stream_key'),
    path('api/stream/start/<str:platform>/', views.api_stream_start, name='api_stream_start'),
    path('api/stream/stop/<str:platform>/', views.api_stream_stop, name='api_stream_stop'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # PROGRAM ROOM APIs (NEU - für das Dashboard)
    # ══════════════════════════════════════════════════════════════════════════
    path('api/program/status/', views.program_room_status_api, name='program_room_status_api'),
    path('api/program/start-stream/', views.program_room_start_stream_api, name='program_room_start_stream_api'),
    path('api/program/stop-stream/', views.program_room_stop_stream_api, name='program_room_stop_stream_api'),
    path('api/program/save-keys/', views.program_room_save_keys_api, name='program_room_save_keys_api'),
    
    # ══════════════════════════════════════════════════════════════════════════
    # AUTHENTIFIZIERUNG
    # ══════════════════════════════════════════════════════════════════════════
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # ══════════════════════════════════════════════════════════════════════════
    # SERIEN-SYSTEM
    # ══════════════════════════════════════════════════════════════════════════
    path('serien/', views.series_list, name='series_list'),
    path('serien/<slug:slug>/', views.series_detail, name='series_detail'),
    path('serien/<slug:series_slug>/staffel-<int:season_number>/', views.season_detail, name='season_detail'),
    path('serien/<slug:series_slug>/staffel-<int:season_number>/episode-<int:episode_number>/', views.episode_player, name='episode_player'),
    path('weiterschauen/', views.continue_watching, name='continue_watching'),

    path("setup-ffmpeg/", views.run_ffmpeg_setup, name="setup_ffmpeg"),
]