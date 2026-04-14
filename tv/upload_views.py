"""
Upload Views für Videos, Bilder und Live-Streams
Unterstützt JDS Cloud Upload API
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Video, Category, LiveStream, AdVideo, SenderLogo
from .jds_upload_service import JDSCloudUploadService


@login_required
@require_http_methods(["GET", "POST"])
def upload_video(request):
    """
    Video-Upload-Seite
    GET: Zeigt Upload-Formular
    POST: Verarbeitet Upload
    """
    if request.method == "GET":
        categories = Category.objects.all()
        return render(request, 'tv/upload_video.html', {
            'categories': categories,
            'page': 'upload'
        })
    
    # POST - File Upload verarbeiten
    if 'video_file' not in request.FILES:
        messages.error(request, "Keine Datei ausgewählt")
        return redirect('upload_video')
    
    video_file = request.FILES['video_file']
    title = request.POST.get('title', video_file.name)
    description = request.POST.get('description', '')
    category_id = request.POST.get('category')
    tags = request.POST.get('tags', '')
    allow_in_mediathek = request.POST.get('allow_in_mediathek') == 'on'
    
    # Upload zur JDS Cloud
    messages.info(request, f"Upload von '{video_file.name}' gestartet... (Bitte warten)")
    
    upload_result = JDSCloudUploadService.upload_video(video_file, title)
    
    if not upload_result:
        messages.error(request, "Upload fehlgeschlagen. Bitte versuchen Sie es erneut.")
        return redirect('upload_video')
    
    # Video-Objekt erstellen
    video = Video(
        title=title,
        description=description,
        source_type='upload',
        source_url='',  # Leer für Uploads
        uploaded_file_id=upload_result.get('id', ''),
        uploaded_file_url=upload_result.get('view_url', ''),
        uploaded_file_download_url=upload_result.get('download_url', ''),
        uploaded_file_name=upload_result.get('name', ''),
        uploaded_file_size=upload_result.get('size', 0),
        uploaded_file_type=upload_result.get('content_type', ''),
        tags=tags,
        allow_in_mediathek=allow_in_mediathek,
        is_active=True,
    )
    
    if category_id:
        try:
            video.category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            pass
    
    video.save()
    
    file_size = JDSCloudUploadService.format_file_size(upload_result.get('size', 0))
    messages.success(
        request, 
        f"Video '{title}' erfolgreich hochgeladen! ({file_size})"
    )
    
    return redirect('mediathek')


@login_required
@require_POST
@csrf_exempt
def upload_video_ajax(request):
    """
    AJAX Video Upload für asynchrone Uploads
    Returns JSON response
    """
    if 'video_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'Keine Datei ausgewählt'
        }, status=400)
    
    video_file = request.FILES['video_file']
    title = request.POST.get('title', video_file.name)
    
    # Upload zur JDS Cloud
    upload_result = JDSCloudUploadService.upload_video(video_file, title)
    
    if not upload_result:
        return JsonResponse({
            'success': False,
            'error': 'Upload fehlgeschlagen'
        }, status=500)
    
    # Video erstellen
    video = Video(
        title=title,
        description=request.POST.get('description', ''),
        source_type='upload',
        source_url='',
        uploaded_file_id=upload_result.get('id', ''),
        uploaded_file_url=upload_result.get('view_url', ''),
        uploaded_file_download_url=upload_result.get('download_url', ''),
        uploaded_file_name=upload_result.get('name', ''),
        uploaded_file_size=upload_result.get('size', 0),
        uploaded_file_type=upload_result.get('content_type', ''),
        is_active=True,
    )
    
    category_id = request.POST.get('category')
    if category_id:
        try:
            video.category = Category.objects.get(id=category_id)
        except:
            pass
    
    video.save()
    
    return JsonResponse({
        'success': True,
        'video': {
            'id': video.id,
            'title': video.title,
            'url': upload_result.get('view_url', ''),
            'download_url': upload_result.get('download_url', ''),
            'size': upload_result.get('size', 0),
            'size_formatted': JDSCloudUploadService.format_file_size(upload_result.get('size', 0)),
        }
    })


@login_required
@require_http_methods(["GET", "POST"])
def upload_thumbnail(request):
    """
    Thumbnail/Bild Upload
    """
    if request.method == "GET":
        return render(request, 'tv/upload_thumbnail.html', {
            'page': 'upload'
        })
    
    if 'image_file' not in request.FILES:
        messages.error(request, "Keine Bilddatei ausgewählt")
        return redirect('upload_thumbnail')
    
    image_file = request.FILES['image_file']
    
    # Upload zur JDS Cloud
    upload_result = JDSCloudUploadService.upload_image(image_file)
    
    if not upload_result:
        messages.error(request, "Bild-Upload fehlgeschlagen")
        return redirect('upload_thumbnail')
    
    # Bild-URL für spätere Verwendung speichern
    messages.success(
        request,
        f"Bild hochgeladen! URL: {upload_result.get('view_url', '')}"
    )
    
    return render(request, 'tv/upload_thumbnail.html', {
        'uploaded_image': upload_result,
        'page': 'upload'
    })


@login_required
@require_POST
def upload_ad_video(request):
    """
    Upload für Werbevideos
    """
    if 'video_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'Keine Datei ausgewählt'
        }, status=400)
    
    video_file = request.FILES['video_file']
    title = request.POST.get('title', video_file.name)
    ad_type = request.POST.get('ad_type', 'spot')
    duration = int(request.POST.get('duration', 30))
    
    # Upload zur JDS Cloud
    upload_result = JDSCloudUploadService.upload_video(video_file, title)
    
    if not upload_result:
        return JsonResponse({
            'success': False,
            'error': 'Upload fehlgeschlagen'
        }, status=500)
    
    # Werbevideo erstellen
    ad_video = AdVideo(
        title=title,
        video_url=upload_result.get('download_url', ''),
        duration=duration,
        ad_type=ad_type,
        is_active=True,
    )
    ad_video.save()
    
    return JsonResponse({
        'success': True,
        'ad_video': {
            'id': ad_video.id,
            'title': ad_video.title,
            'url': upload_result.get('view_url', ''),
            'duration': duration,
            'type': ad_type,
        }
    })


@login_required  
@require_POST
def upload_logo(request):
    """
    Upload für Sender-Logo
    """
    if 'logo_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'Keine Logo-Datei ausgewählt'
        }, status=400)
    
    logo_file = request.FILES['logo_file']
    
    # Upload zur JDS Cloud
    upload_result = JDSCloudUploadService.upload_image(logo_file)
    
    if not upload_result:
        return JsonResponse({
            'success': False,
            'error': 'Logo-Upload fehlgeschlagen'
        }, status=500)
    
    return JsonResponse({
        'success': True,
        'logo': {
            'url': upload_result.get('view_url', ''),
            'download_url': upload_result.get('download_url', ''),
        }
    })


@login_required
@require_http_methods(["GET", "POST"])
def upload_live_stream(request):
    """
    Live-Stream Video/Recording Upload
    """
    if request.method == "GET":
        return render(request, 'tv/upload_livestream.html', {
            'page': 'upload'
        })
    
    if 'stream_file' not in request.FILES:
        messages.error(request, "Keine Stream-Datei ausgewählt")
        return redirect('upload_live_stream')
    
    stream_file = request.FILES['stream_file']
    title = request.POST.get('title', stream_file.name)
    description = request.POST.get('description', '')
    
    # Upload zur JDS Cloud
    upload_result = JDSCloudUploadService.upload_video(stream_file, title)
    
    if not upload_result:
        messages.error(request, "Stream-Upload fehlgeschlagen")
        return redirect('upload_live_stream')
    
    # Als Video in Mediathek speichern (Recording)
    video = Video(
        title=f"[Recording] {title}",
        description=description,
        source_type='upload',
        source_url='',
        uploaded_file_id=upload_result.get('id', ''),
        uploaded_file_url=upload_result.get('view_url', ''),
        uploaded_file_download_url=upload_result.get('download_url', ''),
        uploaded_file_name=upload_result.get('name', ''),
        uploaded_file_size=upload_result.get('size', 0),
        uploaded_file_type=upload_result.get('content_type', ''),
        allow_in_mediathek=True,
        is_active=True,
    )
    video.save()
    
    messages.success(
        request,
        f"Stream-Recording '{title}' erfolgreich hochgeladen!"
    )
    
    return redirect('mediathek')
