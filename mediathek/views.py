from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum
from django.utils.text import slugify
from datetime import timedelta
import json
import uuid
import re

from .models import (
    Category, Video, Series, Season, Episode,
    LiveStream, Playlist, PlaylistItem,
    ViewerSession, ChatMessage,
    Advertisement, AdBreak
)
from rsl_tv import broadcast_api as rsl_api


# ============= HILFSFUNKTIONEN =============

def _local_series():
    """Eigene Serien der Mediathek – werden IMMER angezeigt."""
    return list(
        Series.objects.filter(is_active=True)
        .annotate(
            seasons_count=Count('seasons', filter=Q(seasons__is_active=True), distinct=True),
            episodes_count=Count('seasons__episodes', filter=Q(seasons__episodes__is_active=True), distinct=True),
        )
        .order_by('title')
    )


def _tv_series():
    """Serien aus dem Serien-System des Senders (/serien/)."""
    try:
        from tv.models import Series as TvSeries
        return list(TvSeries.objects.filter(is_active=True).select_related('category').order_by('title'))
    except Exception:
        return []


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _series_cards(local_series, tv_series, api_series):
    """Vereinheitlicht alle Serien-Arten für die Karten-Ansicht.
    Eigene Serien stehen immer zuerst."""
    cards = []
    for s in local_series:
        sub = _plural(s.seasons_count, 'Staffel', 'Staffeln') + ' · ' + _plural(s.episodes_count, 'Folge', 'Folgen')
        cards.append({'href': reverse('mediathek:series_detail', args=[s.slug]), 'title': s.title,
                      'image': s.poster, 'sub': sub, 'badge': 'RSL Original'})
    for s in tv_series:
        parts = [str(s.year)] if s.year else []
        if s.category:
            parts.append(s.category.name)
        cards.append({'href': f'/serien/{s.slug}/', 'title': s.title, 'image': s.poster_url or s.banner_url,
                      'sub': ' · '.join(parts), 'badge': 'RSL Original'})
    for s in api_series:
        sub = ' · '.join(x for x in [s['category'], _plural(s['count'], 'Folge', 'Folgen')] if x)
        cards.append({'href': reverse('mediathek:api_series_detail', args=[s['slug']]), 'title': s['title'],
                      'image': s['thumbnail'], 'sub': sub, 'badge': ''})
    return cards


def _mediathek_context(**extra):
    ctx = {'page': 'mediathek'}
    ctx.update(extra)
    return ctx


# ============= ÖFFENTLICHE SEITEN =============

def home(request):
    current, upcoming = rsl_api.get_now_and_next(4)
    broadcast = rsl_api.get_broadcast()
    studios_live = [s for s in rsl_api.get_studios() if s['is_active']]
    library = rsl_api.get_library()
    news = rsl_api.get_news()
    api_series = rsl_api.get_api_series()

    context = _mediathek_context(
        page_title='Mediathek',
        current_show=current,
        upcoming=upcoming,
        broadcast=broadcast,
        studios_live=studios_live,
        live_streams=LiveStream.objects.filter(is_active=True, is_live=True),
        series_cards=_series_cards(_local_series(), _tv_series(), api_series),
        library=library[:12],
        library_total=len(library),
        news=news[:6],
        singles=rsl_api.get_single_programs()[:12],
        videos=Video.objects.filter(is_active=True).order_by('-published_at')[:12],
        categories=Category.objects.filter(is_active=True),
        api_categories=rsl_api.get_categories(),
    )
    return render(request, 'mediathek/home.html', context)


def video_list(request):
    videos = Video.objects.filter(is_active=True).order_by('-published_at')
    category = request.GET.get('category')
    if category:
        videos = videos.filter(category__slug=category)

    context = _mediathek_context(
        page_title='Videos',
        videos=videos,
        categories=Category.objects.filter(is_active=True),
        current_category=category,
    )
    return render(request, 'mediathek/video_list.html', context)


def video_player(request, slug):
    video = get_object_or_404(Video, slug=slug, is_active=True)
    Video.objects.filter(pk=video.pk).update(views=video.views + 1)

    related = Video.objects.filter(is_active=True).exclude(id=video.id)
    if video.category_id:
        related = related.filter(category=video.category)
    context = _mediathek_context(
        page_title=video.title,
        video=video,
        related=related.order_by('-published_at')[:8],
    )
    return render(request, 'mediathek/video_player.html', context)


def series_list(request):
    context = _mediathek_context(
        page_title='Serien',
        series_cards=_series_cards(_local_series(), _tv_series(), rsl_api.get_api_series()),
    )
    return render(request, 'mediathek/series_list.html', context)


def series_detail(request, slug):
    series = get_object_or_404(Series, slug=slug, is_active=True)
    seasons = series.seasons.filter(is_active=True).order_by('season_number').prefetch_related('episodes')
    first_episode = Episode.objects.filter(
        season__series=series, season__is_active=True, is_active=True
    ).order_by('season__season_number', 'episode_number').first()

    context = _mediathek_context(
        page_title=series.title,
        series=series,
        seasons=seasons,
        first_episode=first_episode,
    )
    return render(request, 'mediathek/series_detail.html', context)


def season_detail(request, series_slug, season_number):
    series = get_object_or_404(Series, slug=series_slug, is_active=True)
    season = get_object_or_404(Season, series=series, season_number=season_number, is_active=True)
    episodes = season.episodes.filter(is_active=True).order_by('episode_number')

    context = _mediathek_context(
        page_title=f"{series.title} – Staffel {season_number}",
        series=series,
        season=season,
        seasons=series.seasons.filter(is_active=True).order_by('season_number'),
        episodes=episodes,
    )
    return render(request, 'mediathek/season_detail.html', context)


def episode_player(request, series_slug, season_number, episode_number):
    series = get_object_or_404(Series, slug=series_slug, is_active=True)
    season = get_object_or_404(Season, series=series, season_number=season_number, is_active=True)
    episode = get_object_or_404(Episode, season=season, episode_number=episode_number, is_active=True)

    all_eps = list(
        Episode.objects.filter(season__series=series, season__is_active=True, is_active=True)
        .select_related('season').order_by('season__season_number', 'episode_number')
    )
    idx = next((i for i, e in enumerate(all_eps) if e.pk == episode.pk), 0)

    context = _mediathek_context(
        page_title=f"{series.title} – S{season_number} E{episode_number}",
        series=series,
        season=season,
        episode=episode,
        prev_episode=all_eps[idx - 1] if idx > 0 else None,
        next_episode=all_eps[idx + 1] if idx + 1 < len(all_eps) else None,
        season_episodes=[e for e in all_eps if e.season_id == season.pk],
    )
    return render(request, 'mediathek/episode_player.html', context)


# ── Inhalte aus der RSL Broadcast-API ──

def api_series_detail(request, slug):
    series = rsl_api.get_api_series_by_slug(slug)
    if not series:
        raise Http404("Serie nicht gefunden")
    context = _mediathek_context(page_title=series['title'], series=series)
    return render(request, 'mediathek/api_series_detail.html', context)


def program_player(request, program_id):
    program_id = str(program_id)
    program = rsl_api.get_program(program_id)
    if not program:
        raise Http404("Sendung nicht gefunden")

    if program['series_title']:
        series = rsl_api.get_api_series_by_slug(program['series_slug'])
        episodes = series['episodes'] if series else []
        idx = next((i for i, e in enumerate(episodes) if e['id'] == program['id']), 0)
        prev_ep = episodes[idx - 1] if idx > 0 else None
        next_ep = episodes[idx + 1] if idx + 1 < len(episodes) else None
        more = episodes
    else:
        series, prev_ep, next_ep = None, None, None
        more = [p for p in rsl_api.get_single_programs()
                if p['category'] == program['category'] and p['id'] != program['id']][:12]

    context = _mediathek_context(
        page_title=program['title'],
        program=program,
        series=series,
        prev_episode=prev_ep,
        next_episode=next_ep,
        more=more,
    )
    return render(request, 'mediathek/program_player.html', context)


def library_list(request):
    items = rsl_api.get_library()
    reihe = request.GET.get('reihe', '')
    reihen = sorted({i['series_title'] for i in items if i['series_title']})
    if reihe:
        items = [i for i in items if slugify(i['series_title']) == reihe]
    context = _mediathek_context(
        page_title='Sendungen verpasst?',
        items=items,
        reihen=[{'slug': slugify(r), 'name': r} for r in reihen],
        current_reihe=reihe,
    )
    return render(request, 'mediathek/library_list.html', context)


def library_player(request, item_id):
    item_id = str(item_id)
    item = rsl_api.get_library_item(item_id)
    if not item:
        # Nachrichten-Ausgaben haben ebenfalls eine Ausgaben-ID
        if rsl_api.get_edition(item_id):
            return redirect('mediathek:edition_detail', edition_id=item_id)
        raise Http404("Ausgabe nicht gefunden")
    more = [i for i in rsl_api.get_library() if i['id'] != item_id][:12]
    context = _mediathek_context(page_title=item['title'], item=item, more=more)
    return render(request, 'mediathek/library_player.html', context)


def news_list(request):
    context = _mediathek_context(page_title='Nachrichten', news=rsl_api.get_news(), page='news')
    return render(request, 'mediathek/news_list.html', context)


def edition_detail(request, edition_id):
    edition_id = str(edition_id)
    edition = rsl_api.get_edition(edition_id)
    if not edition:
        raise Http404("Ausgabe nicht gefunden")
    more = [n for n in rsl_api.get_news() if n['id'] != edition_id][:8]
    context = _mediathek_context(page_title=edition['title'], edition=edition, more=more, page='news')
    return render(request, 'mediathek/edition_detail.html', context)


def studio_player(request, studio_id):
    studio_id = str(studio_id)
    studio = rsl_api.get_studio(studio_id)
    if not studio:
        raise Http404("Studio nicht gefunden")
    context = _mediathek_context(
        page_title=studio['name'],
        studio=studio,
        other_studios=[s for s in rsl_api.get_studios() if s['id'] != studio_id],
    )
    return render(request, 'mediathek/studio_player.html', context)


def api_category(request, slug):
    cat = next((c for c in rsl_api.get_categories() if c['slug'] == slug), None)
    if not cat:
        raise Http404("Rubrik nicht gefunden")
    programs = [p for p in rsl_api.get_programs()
                if slugify(p['category']) == slug and p['video_type'] != 'ai_news']
    series = [s for s in rsl_api.get_api_series() if slugify(s['category']) == slug]
    series_slugs = {s['slug'] for s in series}
    context = _mediathek_context(
        page_title=cat['name'],
        category=cat,
        series_cards=_series_cards([], [], series),
        programs=[p for p in programs if p['series_slug'] not in series_slugs],
    )
    return render(request, 'mediathek/api_category.html', context)


# ── Live ──

def live_overview(request):
    current, upcoming = rsl_api.get_now_and_next(6)
    context = _mediathek_context(
        page_title='Live',
        live_streams=LiveStream.objects.filter(is_active=True, is_live=True),
        upcoming_streams=LiveStream.objects.filter(
            is_active=True, is_live=False, scheduled_start__gte=timezone.now()
        ).order_by('scheduled_start'),
        studios=rsl_api.get_studios(),
        broadcast=rsl_api.get_broadcast(),
        current_show=current,
        upcoming=upcoming,
    )
    return render(request, 'mediathek/live_overview.html', context)


def _live_player_source(stream, request):
    """Bestimmt, wie ein Livestream eingebettet wird: ('iframe'|'hls', url)."""
    url = stream.stream_url or ''
    if 'rsl-studio-live' in url:
        return {'kind': 'iframe', 'src': url}
    yt = rsl_api.youtube_id(url)
    if yt:
        return {'kind': 'iframe', 'src': f'https://www.youtube-nocookie.com/embed/{yt}?autoplay=1&rel=0'}
    if stream.source_type == 'twitch' or 'twitch.tv' in url:
        channel = url.rstrip('/').split('/')[-1]
        host = request.get_host().split(':')[0]
        return {'kind': 'iframe', 'src': f'https://player.twitch.tv/?channel={channel}&parent={host}&autoplay=true'}
    return {'kind': 'hls', 'src': url}


def live_player(request, slug):
    stream = get_object_or_404(LiveStream, slug=slug, is_active=True)

    session_id = request.session.get('viewer_session')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['viewer_session'] = session_id

    viewer, created = ViewerSession.objects.get_or_create(
        session_id=session_id,
        defaults={'stream': stream, 'ip_address': request.META.get('REMOTE_ADDR')}
    )
    if not created:
        viewer.stream = stream
        viewer.last_heartbeat = timezone.now()
        viewer.save()

    context = _mediathek_context(
        page_title=stream.title,
        stream=stream,
        viewer_session=session_id,
        player=_live_player_source(stream, request),
    )
    return render(request, 'mediathek/live_player.html', context)


def playlist_list(request):
    playlists = Playlist.objects.filter(is_active=True).annotate(items_count=Count('items'))
    context = _mediathek_context(page_title='Playlists', playlists=playlists)
    return render(request, 'mediathek/playlist_list.html', context)


def playlist_detail(request, slug):
    playlist = get_object_or_404(Playlist, slug=slug, is_active=True)
    items = playlist.items.select_related('video').filter(video__is_active=True).order_by('order')
    context = _mediathek_context(page_title=playlist.title, playlist=playlist, items=items)
    return render(request, 'mediathek/playlist_detail.html', context)


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    videos = Video.objects.filter(category=category, is_active=True).order_by('-published_at')
    context = _mediathek_context(page_title=category.name, category=category, videos=videos)
    return render(request, 'mediathek/category_detail.html', context)


def search(request):
    query = request.GET.get('q', '').strip()
    videos, local_series, api_series, programs = [], [], [], []

    if query:
        videos = Video.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query), is_active=True
        )[:40]
        local_series = [s for s in _local_series()
                        if query.lower() in s.title.lower() or query.lower() in s.description.lower()]
        api_series, programs = rsl_api.search(query)

    context = _mediathek_context(
        page_title='Suche',
        search_query=query,
        videos=videos,
        series_cards=_series_cards(local_series, [], api_series),
        programs=programs[:60],
        total=len(videos) + len(local_series) + len(api_series) + len(programs),
    )
    return render(request, 'mediathek/search.html', context)


# ============= API ENDPOINTS (unverändert) =============

@csrf_exempt
@require_http_methods(["POST"])
def api_viewer_heartbeat(request):
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        stream_slug = data.get('stream_slug')
        
        stream = LiveStream.objects.get(slug=stream_slug)
        viewer = ViewerSession.objects.get(stream=stream, session_id=session_id)
        viewer.last_heartbeat = timezone.now()
        viewer.save()
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def api_viewer_count(request, stream_slug):
    stream = get_object_or_404(LiveStream, slug=stream_slug)
    count = stream.get_current_viewers()
    return JsonResponse({'count': count})


@csrf_exempt
@require_http_methods(["POST"])
def api_chat_send(request):
    try:
        data = json.loads(request.body)
        stream_slug = data.get('stream_slug')
        username = data.get('username', 'Gast')
        message = data.get('message', '')
        
        stream = LiveStream.objects.get(slug=stream_slug)
        
        chat_message = ChatMessage.objects.create(
            stream=stream,
            username=username,
            message=message
        )
        
        return JsonResponse({
            'status': 'ok',
            'message': {
                'id': chat_message.id,
                'username': chat_message.username,
                'message': chat_message.message,
                'timestamp': chat_message.timestamp.isoformat()
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def api_chat_messages(request, stream_slug):
    stream = get_object_or_404(LiveStream, slug=stream_slug)
    messages_qs = stream.messages.order_by('-timestamp')[:50]
    
    messages_list = [{
        'id': msg.id,
        'username': msg.username,
        'message': msg.message,
        'timestamp': msg.timestamp.isoformat(),
        'is_system': msg.is_system
    } for msg in reversed(messages_qs)]
    
    return JsonResponse({'messages': messages_list})


def api_get_ads(request, content_type, content_id):
    # Werbung-API bleibt gleich
    return JsonResponse({'ads': []})


@csrf_exempt
def api_ad_click(request):
    return JsonResponse({'status': 'ok'})


# ============= CUSTOM ADMIN VIEWS (NEU) =============

@staff_member_required
def custom_admin_dashboard(request):
    """Custom Admin Dashboard - Übersicht"""
    
    # Statistiken
    stats = {
        'videos_count': Video.objects.filter(is_active=True).count(),
        'series_count': Series.objects.filter(is_active=True).count(),
        'categories_count': Category.objects.filter(is_active=True).count(),
        'playlists_count': Playlist.objects.filter(is_active=True).count(),
        'live_now': LiveStream.objects.filter(is_live=True).count(),
        'total_views': Video.objects.aggregate(Sum('views'))['views__sum'] or 0,
    }
    
    # Letzte Videos
    recent_videos = Video.objects.filter(is_active=True).order_by('-created_at')[:5]
    
    # Live Streams
    live_streams = LiveStream.objects.filter(is_live=True)
    
    # Ablaufende Inhalte (nächste 7 Tage)
    expiring_soon = []
    week_from_now = timezone.now() + timedelta(days=7)
    
    expiring_videos = Video.objects.filter(
        is_active=True,
        available_until__lte=week_from_now,
        available_until__gte=timezone.now()
    )
    expiring_series = Series.objects.filter(
        is_active=True,
        available_until__lte=week_from_now,
        available_until__gte=timezone.now()
    )
    
    for video in expiring_videos:
        expiring_soon.append({
            'type': 'Video',
            'title': video.title,
            'expires': video.available_until
        })
    
    for series in expiring_series:
        expiring_soon.append({
            'type': 'Serie',
            'title': series.title,
            'expires': series.available_until
        })
    
    context = {
        'page_title': 'Admin Dashboard',
        'stats': stats,
        'recent_videos': recent_videos,
        'live_streams': live_streams,
        'expiring_soon': expiring_soon,
    }
    return render(request, 'mediathek/admin/dashboard.html', context)


@staff_member_required
def custom_admin_videos(request):
    """Video-Verwaltung"""
    videos = Video.objects.all().order_by('-created_at')
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'page_title': 'Video-Verwaltung',
        'videos': videos,
        'categories': categories,
    }
    return render(request, 'mediathek/admin/videos.html', context)


@staff_member_required
def custom_admin_video_edit(request, video_id=None):
    """Video bearbeiten/erstellen"""
    video = None
    if video_id:
        video = get_object_or_404(Video, id=video_id)
    
    if request.method == 'POST':
        # Video speichern
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        source_url = request.POST.get('source_url')
        category_id = request.POST.get('category')
        available_until = request.POST.get('available_until')
        is_active = request.POST.get('is_active') == 'on'
        
        if video:
            video.title = title
            video.description = description
            video.source_url = source_url
            video.is_active = is_active
            if category_id:
                video.category_id = category_id
            if available_until:
                video.available_until = available_until
            video.save()
            messages.success(request, f'Video "{title}" aktualisiert!')
        else:
            video = Video.objects.create(
                title=title,
                description=description,
                source_url=source_url,
                category_id=category_id if category_id else None,
                available_until=available_until if available_until else None,
                is_active=is_active
            )
            messages.success(request, f'Video "{title}" erstellt!')
        
        return redirect('mediathek:custom_admin_videos')
    
    categories = Category.objects.filter(is_active=True)
    context = {
        'page_title': 'Video bearbeiten' if video else 'Neues Video',
        'video': video,
        'categories': categories,
    }
    return render(request, 'mediathek/admin/video_edit.html', context)


@staff_member_required
def custom_admin_playlists(request):
    """Playlist-Verwaltung mit YouTube Import"""
    playlists = Playlist.objects.all().order_by('-id')
    
    context = {
        'page_title': 'Playlist-Verwaltung',
        'playlists': playlists,
    }
    return render(request, 'mediathek/admin/playlists.html', context)


@staff_member_required
def custom_admin_playlist_edit(request, playlist_id=None):
    """Playlist bearbeiten/erstellen"""
    playlist = None
    if playlist_id:
        playlist = get_object_or_404(Playlist, id=playlist_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        youtube_url = request.POST.get('youtube_playlist_url', '')
        auto_import = request.POST.get('auto_import') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        if playlist:
            playlist.title = title
            playlist.description = description
            playlist.youtube_playlist_url = youtube_url
            playlist.auto_import = auto_import
            playlist.is_active = is_active
            playlist.save()
            messages.success(request, f'Playlist "{title}" aktualisiert!')
        else:
            playlist = Playlist.objects.create(
                title=title,
                description=description,
                youtube_playlist_url=youtube_url,
                auto_import=auto_import,
                is_active=is_active
            )
            messages.success(request, f'Playlist "{title}" erstellt!')
        
        return redirect('mediathek:custom_admin_playlists')
    
    context = {
        'page_title': 'Playlist bearbeiten' if playlist else 'Neue Playlist',
        'playlist': playlist,
    }
    return render(request, 'mediathek/admin/playlist_edit.html', context)


@staff_member_required
def custom_admin_youtube_import(request, playlist_id):
    """YouTube Playlist Import"""
    playlist = get_object_or_404(Playlist, id=playlist_id)
    
    if not playlist.youtube_playlist_url:
        messages.error(request, 'Keine YouTube-URL vorhanden!')
        return redirect('mediathek:custom_admin_playlists')
    
    # Importiere YouTube Playlist
    from .youtube_import import import_youtube_playlist_simple
    
    success, message, videos_imported = import_youtube_playlist_simple(playlist)
    
    if success:
        messages.success(request, f'✅ {message} ({videos_imported} Videos)')
    else:
        messages.error(request, f'❌ {message}')
    
    return redirect('mediathek:custom_admin_playlists')


@staff_member_required
def custom_admin_youtube_debug(request):
    """YouTube URL Debugger"""
    test_result = None
    
    if request.method == 'POST':
        test_url = request.POST.get('test_url')
        
        from .youtube_import import (
            extract_playlist_id, 
            get_playlist_from_json,
            scrape_all_video_ids
        )
        
        playlist_id = extract_playlist_id(test_url)
        
        videos = []
        errors = []
        
        if playlist_id:
            # Versuche Methode 1
            videos = get_playlist_from_json(playlist_id)
            
            # Versuche Methode 2 als Fallback
            if not videos:
                errors.append("Methode 1 (JSON) fehlgeschlagen")
                videos = scrape_all_video_ids(playlist_id)
                
                if videos:
                    errors.append("Methode 2 (Aggressives Scraping) erfolgreich")
                else:
                    errors.append("Methode 2 (Aggressives Scraping) fehlgeschlagen")
        else:
            errors.append("Keine Playlist-ID in URL gefunden")
        
        test_result = {
            'url': test_url,
            'playlist_id': playlist_id,
            'video_count': len(videos),
            'videos': videos[:10],  # Max 10 anzeigen
            'errors': errors if not videos else []
        }
    
    context = {
        'page_title': 'YouTube Debugger',
        'test_result': test_result,
    }
    return render(request, 'mediathek/admin/youtube_debug.html', context)


@staff_member_required
def custom_admin_manual_import(request):
    """Manueller Video-Import"""
    
    if request.method == 'POST':
        playlist_id = request.POST.get('playlist_id')
        video_urls = request.POST.get('video_urls', '')
        
        if not playlist_id or not video_urls:
            messages.error(request, 'Bitte Playlist und Video-URLs angeben!')
            return redirect('mediathek:custom_admin_manual_import')
        
        playlist = get_object_or_404(Playlist, id=playlist_id)
        
        # URLs aufteilen
        urls = [url.strip() for url in video_urls.split('\n') if url.strip()]
        
        from .youtube_import import import_from_video_list
        
        videos_data = import_from_video_list(urls)
        
        if not videos_data:
            messages.error(request, 'Keine Videos gefunden! URLs korrekt?')
            return redirect('mediathek:custom_admin_manual_import')
        
        # Videos importieren
        imported_count = 0
        for idx, video_data in enumerate(videos_data):
            try:
                video, created = Video.objects.get_or_create(
                    source_url=video_data['url'],
                    defaults={
                        'title': video_data['title'][:250],
                        'thumbnail': video_data['thumbnail'],
                        'source_type': 'youtube',
                        'is_active': True,
                    }
                )
                
                PlaylistItem.objects.get_or_create(
                    playlist=playlist,
                    video=video,
                    defaults={'order': idx}
                )
                
                imported_count += 1
            except:
                continue
        
        messages.success(request, f'✅ {imported_count} Videos erfolgreich importiert!')
        return redirect('mediathek:custom_admin_playlists')
    
    playlists = Playlist.objects.all().order_by('-id')
    
    context = {
        'page_title': 'Manueller Import',
        'playlists': playlists,
    }
    return render(request, 'mediathek/admin/manual_import.html', context)


@staff_member_required
def custom_admin_series(request):
    """Serien-Verwaltung"""
    series = Series.objects.all().order_by('-id')
    
    context = {
        'page_title': 'Serien-Verwaltung',
        'series': series,
    }
    return render(request, 'mediathek/admin/series.html', context)


@staff_member_required
def custom_admin_livestreams(request):
    """Livestream-Verwaltung"""
    streams = LiveStream.objects.all().order_by('-created_at')
    
    context = {
        'page_title': 'Livestream-Verwaltung',
        'streams': streams,
    }
    return render(request, 'mediathek/admin/livestreams.html', context)
