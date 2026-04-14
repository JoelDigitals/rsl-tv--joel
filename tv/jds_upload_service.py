"""
JDS Cloud Upload Service
Handles file uploads to JDS Cloud API
"""
import requests
from typing import Dict, Any, Optional
from django.core.files.uploadedfile import UploadedFile


class JDSCloudUploadService:
    """Service für File-Uploads zur JDS Cloud"""
    
    UPLOAD_ENDPOINT = "https://ppkinjwiewiynqgofdcz.supabase.co/functions/v1/upload"
    AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBwa2luandpZXdpeW5xZ29mZGN6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4NDY2MTksImV4cCI6MjA5MTQyMjYxOX0.hSU2FfTONOrOZrbBOASoAXlx7W3ePg3tsHj-VaCg-Jo"
    
    @classmethod
    def upload_file(cls, file: UploadedFile) -> Optional[Dict[str, Any]]:
        """
        Upload a file to JDS Cloud
        
        Args:
            file: Django UploadedFile object
            
        Returns:
            Dict with upload result or None on error:
            {
                "success": True,
                "file": {
                    "id": "uuid",
                    "name": "filename.mp4",
                    "size": 1234567,
                    "content_type": "video/mp4",
                    "view_url": "https://...",
                    "download_url": "https://...",
                    "created_at": "2026-04-10T..."
                }
            }
        """
        try:
            headers = {
                "Authorization": f"Bearer {cls.AUTH_TOKEN}"
            }
            
            files = {
                "file": (file.name, file, file.content_type)
            }
            
            response = requests.post(
                cls.UPLOAD_ENDPOINT,
                headers=headers,
                files=files,
                timeout=300  # 5 Minuten für große Dateien
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Upload failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Upload exception: {str(e)}")
            return None
    
    @classmethod
    def upload_video(cls, file: UploadedFile, title: str = None) -> Optional[Dict[str, Any]]:
        """
        Upload a video file with metadata
        
        Args:
            file: Video file to upload
            title: Optional video title
            
        Returns:
            Upload result dict or None
        """
        result = cls.upload_file(file)
        
        if result and result.get('success'):
            file_data = result.get('file', {})
            
            # Füge zusätzliche Metadaten hinzu
            file_data['title'] = title or file_data.get('name', 'Untitled')
            file_data['is_video'] = cls.is_video_file(file_data.get('content_type', ''))
            
            return file_data
        
        return None
    
    @classmethod
    def upload_image(cls, file: UploadedFile) -> Optional[Dict[str, Any]]:
        """
        Upload an image file
        
        Args:
            file: Image file to upload
            
        Returns:
            Upload result dict or None
        """
        result = cls.upload_file(file)
        
        if result and result.get('success'):
            file_data = result.get('file', {})
            file_data['is_image'] = cls.is_image_file(file_data.get('content_type', ''))
            return file_data
        
        return None
    
    @staticmethod
    def is_video_file(content_type: str) -> bool:
        """Check if content type is a video"""
        video_types = [
            'video/mp4',
            'video/mpeg',
            'video/quicktime',
            'video/x-msvideo',
            'video/x-ms-wmv',
            'video/webm',
            'video/x-matroska',
            'video/3gpp',
            'application/x-mpegURL',  # HLS
            'video/MP2T',  # MPEG-TS
        ]
        return content_type.lower() in [vt.lower() for vt in video_types]
    
    @staticmethod
    def is_image_file(content_type: str) -> bool:
        """Check if content type is an image"""
        image_types = [
            'image/jpeg',
            'image/jpg',
            'image/png',
            'image/gif',
            'image/webp',
            'image/svg+xml',
            'image/bmp',
        ]
        return content_type.lower() in [it.lower() for it in image_types]
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
