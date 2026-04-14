"""
Upload Center View
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def upload_center(request):
    """
    Upload Center Dashboard
    Zeigt alle Upload-Optionen an
    """
    return render(request, 'tv/upload_center.html', {
        'page': 'upload'
    })
