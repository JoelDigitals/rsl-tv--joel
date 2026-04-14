"""
RSL Mediathek - Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from .models import (
    Category, Video, Series, Season, Episode,
    LiveStream, Playlist, PlaylistItem
)


# ══════════════════════════════════════════════════════════════════════════════
# HAUPT-MEDIATHEK
# ══════════════════════════════════════════════════════════════════════════════

def mediathek_home(request):
    """Haupt-Mediathek Übersicht"""
    # Featured Content
    featured_series = Series.objects.filter(is_active=True, featured=True)[:4]
    featured_videos = Video.objects.filter(is_active=True, featured=True)[:4]
    
    # Live-Streams
    live_streams = LiveStream.objects.filter(is_live=True, is_active=True)
    
    # Neueste Videos
    latest_videos = Video.objects.filter(is_active=True).order_by('-published_at')[:12]
    
    # Kategorien mit Counts
    categories = Category.objects.filter(is_active=True).annotate(
        video_count=Count('videos', filter=Q(videos__is_active=True))
    ).order_by('order')
    
    # Neueste Serien
    latest_series = Series.objects.filter(is_active=True).order_by('-created_at')[:8]
    
    context = {
        'featured_series': featured_series,
        'featured_videos': featured_videos,
        'live_streams': live_streams,
        'latest_videos': latest_videos,
        'categories': categories,
        'latest_series': latest_series,
        'page_title': 'Mediathek',
    }
    
    return render(request, 'mediathek/home.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# VIDEOS
# ══════════════════════════════════════════════════════════════════════════════

def video_list(request):
    """Alle Videos anzeigen mit Filter"""
    videos = Video.objects.filter(is_active=True).select_related('category')
    
    # Kategorie-Filter
    category_slug = request.GET.get('category')
    if category_slug:
        videos = videos.filter(category__slug=category_slug)
    
    # Suche
    query = request.GET.get('q')
    if query:
        videos = videos.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query)
        )
    
    # Source-Filter
    source = request.GET.get('source')
    if source:
        videos = videos.filter(source_type=source)
    
    videos = videos.order_by('-published_at')
    
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'videos': videos,
        'categories': categories,
        'current_category': category_slug,
        'search_query': query,
        'current_source': source,
        'page_title': 'Videos',
    }
    
    return render(request, 'mediathek/video_list.html', context)


def video_player(request, slug):
    """Video-Player"""
    video = get_object_or_404(Video, slug=slug, is_active=True)
    
    # View-Counter erhöhen
    video.increment_views()
    
    # Ähnliche Videos
    related_videos = Video.objects.filter(
        is_active=True,
        category=video.category
    ).exclude(id=video.id).order_by('?')[:6]
    
    context = {
        'video': video,
        'related_videos': related_videos,
        'page_title': video.title,
    }
    
    return render(request, 'mediathek/video_player.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# SERIEN
# ══════════════════════════════════════════════════════════════════════════════

def series_list(request):
    """Alle Serien anzeigen"""
    series = Series.objects.filter(is_active=True)
    
    # Kategorie-Filter
    category_slug = request.GET.get('category')
    if category_slug:
        series = series.filter(category__slug=category_slug)
    
    # Suche
    query = request.GET.get('q')
    if query:
        series = series.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query)
        )
    
    series = series.order_by('-created_at')
    
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'series': series,
        'categories': categories,
        'current_category': category_slug,
        'search_query': query,
        'page_title': 'Serien',
    }
    
    return render(request, 'mediathek/series_list.html', context)


def series_detail(request, slug):
    """Serien-Detail mit allen Staffeln"""
    series = get_object_or_404(Series, slug=slug, is_active=True)
    
    seasons = series.seasons.filter(is_active=True).prefetch_related(
        Prefetch('episodes', queryset=Episode.objects.filter(is_active=True).order_by('episode_number'))
    ).order_by('season_number')
    
    latest_episode = series.latest_episode()
    
    context = {
        'series': series,
        'seasons': seasons,
        'latest_episode': latest_episode,
        'page_title': series.title,
    }
    
    return render(request, 'mediathek/series_detail.html', context)


def season_detail(request, series_slug, season_number):
    """Staffel-Detail mit allen Episoden"""
    series = get_object_or_404(Series, slug=series_slug, is_active=True)
    season = get_object_or_404(Season, series=series, season_number=season_number, is_active=True)
    
    episodes = season.episodes.filter(is_active=True).order_by('episode_number')
    
    # Navigation
    prev_season = Season.objects.filter(
        series=series,
        season_number__lt=season_number,
        is_active=True
    ).order_by('-season_number').first()
    
    next_season = Season.objects.filter(
        series=series,
        season_number__gt=season_number,
        is_active=True
    ).order_by('season_number').first()
    
    context = {
        'series': series,
        'season': season,
        'episodes': episodes,
        'prev_season': prev_season,
        'next_season': next_season,
        'page_title': f"{series.title} - Staffel {season_number}",
    }
    
    return render(request, 'mediathek/season_detail.html', context)


def episode_player(request, series_slug, season_number, episode_number):
    """Episode abspielen"""
    series = get_object_or_404(Series, slug=series_slug, is_active=True)
    season = get_object_or_404(Season, series=series, season_number=season_number, is_active=True)
    episode = get_object_or_404(Episode, season=season, episode_number=episode_number, is_active=True)
    
    # Navigation
    next_episode = episode.next_episode()
    prev_episode = episode.previous_episode()
    
    # Andere Episoden dieser Staffel
    other_episodes = season.episodes.filter(is_active=True).exclude(id=episode.id).order_by('episode_number')[:6]
    
    context = {
        'series': series,
        'season': season,
        'episode': episode,
        'next_episode': next_episode,
        'prev_episode': prev_episode,
        'other_episodes': other_episodes,
        'page_title': f"{series.title} S{season_number:02d}E{episode_number:02d}",
    }
    
    return render(request, 'mediathek/episode_player.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# LIVE-STREAMS
# ══════════════════════════════════════════════════════════════════════════════

def live_overview(request):
    """Live-Streams Übersicht"""
    live_now = LiveStream.objects.filter(is_live=True, is_active=True)
    upcoming = LiveStream.objects.filter(
        is_live=False,
        is_active=True,
        scheduled_start__isnull=False
    ).order_by('scheduled_start')[:10]
    
    context = {
        'live_now': live_now,
        'upcoming': upcoming,
        'page_title': 'Live & Programm',
    }
    
    return render(request, 'mediathek/live_overview.html', context)


def live_player(request, slug):
    """Live-Stream Player"""
    stream = get_object_or_404(LiveStream, slug=slug, is_active=True)
    
    context = {
        'stream': stream,
        'page_title': stream.title,
    }
    
    return render(request, 'mediathek/live_player.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# PLAYLISTS
# ══════════════════════════════════════════════════════════════════════════════

def playlist_list(request):
    """Alle öffentlichen Playlists"""
    playlists = Playlist.objects.filter(is_public=True, is_active=True).select_related('created_by')
    
    context = {
        'playlists': playlists,
        'page_title': 'Playlists',
    }
    
    return render(request, 'mediathek/playlist_list.html', context)


def playlist_detail(request, slug):
    """Playlist-Detail"""
    playlist = get_object_or_404(Playlist, slug=slug, is_public=True, is_active=True)
    
    items = playlist.items.select_related('video__category').order_by('order')
    
    context = {
        'playlist': playlist,
        'items': items,
        'page_title': playlist.title,
    }
    
    return render(request, 'mediathek/playlist_detail.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# KATEGORIE
# ══════════════════════════════════════════════════════════════════════════════

def category_detail(request, slug):
    """Kategorie-Übersicht mit Videos und Serien"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    
    videos = Video.objects.filter(category=category, is_active=True).order_by('-published_at')[:20]
    series = Series.objects.filter(category=category, is_active=True).order_by('-created_at')[:12]
    
    context = {
        'category': category,
        'videos': videos,
        'series': series,
        'page_title': category.name,
    }
    
    return render(request, 'mediathek/category_detail.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# SUCHE
# ══════════════════════════════════════════════════════════════════════════════

def search(request):
    """Globale Suche"""
    query = request.GET.get('q', '')
    
    if not query:
        return redirect('mediathek:home')
    
    # Videos suchen
    videos = Video.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__icontains=query),
        is_active=True
    )[:20]
    
    # Serien suchen
    series = Series.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__icontains=query),
        is_active=True
    )[:12]
    
    # Live-Streams suchen
    streams = LiveStream.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query),
        is_active=True
    )[:6]
    
    context = {
        'query': query,
        'videos': videos,
        'series': series,
        'streams': streams,
        'page_title': f'Suche: {query}',
    }
    
    return render(request, 'mediathek/search.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS (für AJAX)
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def api_videos(request):
    """API: Videos als JSON"""
    videos = Video.objects.filter(is_active=True).select_related('category')[:50]
    
    data = [{
        'id': v.id,
        'title': v.title,
        'slug': v.slug,
        'thumbnail': v.get_thumbnail(),
        'duration': v.duration_display(),
        'category': v.category.name if v.category else None,
        'source_type': v.source_type,
        'published_at': v.published_at.strftime('%d.%m.%Y'),
        'url': f'/mediathek/videos/{v.slug}/'
    } for v in videos]
    
    return JsonResponse({'videos': data})


@require_GET
def api_series(request):
    """API: Serien als JSON"""
    series = Series.objects.filter(is_active=True)[:50]
    
    data = [{
        'id': s.id,
        'title': s.title,
        'slug': s.slug,
        'poster': s.get_poster(),
        'year': s.year,
        'rating': float(s.rating) if s.rating else None,
        'seasons_count': s.seasons_count(),
        'episodes_count': s.episodes_count(),
        'url': f'/mediathek/serien/{s.slug}/'
    } for s in series]
    
    return JsonResponse({'series': data})


@require_GET
def api_live(request):
    """API: Live-Streams als JSON"""
    live_streams = LiveStream.objects.filter(is_live=True, is_active=True)
    
    data = [{
        'id': ls.id,
        'title': ls.title,
        'slug': ls.slug,
        'thumbnail': ls.get_thumbnail(),
        'viewers': ls.viewers,
        'is_live': ls.is_live,
        'url': f'/mediathek/live/{ls.slug}/'
    } for ls in live_streams]
    
    return JsonResponse({'streams': data})
