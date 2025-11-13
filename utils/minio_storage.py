"""
MinIO storage utility for uploading and managing profile images.
"""
import logging
import io
from typing import Optional
from minio import Minio
from minio.error import S3Error
from config.settings import settings

logger = logging.getLogger(__name__)

# Global MinIO client instance
_minio_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Get or create MinIO client instance."""
    global _minio_client
    if _minio_client is None:
        endpoint = settings.MINIO_ENDPOINT
        # Remove http:// or https:// if present
        if endpoint.startswith('http://'):
            endpoint = endpoint[7:]
        elif endpoint.startswith('https://'):
            endpoint = endpoint[8:]
        
        _minio_client = Minio(
            endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL
        )
        
        # Ensure bucket exists and is public
        try:
            if not _minio_client.bucket_exists(settings.MINIO_BUCKET_NAME):
                _minio_client.make_bucket(settings.MINIO_BUCKET_NAME)
                logger.info(f"Created MinIO bucket: {settings.MINIO_BUCKET_NAME}")
            
            # Set bucket policy to allow public read access
            try:
                import json
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET_NAME}/*"]
                        }
                    ]
                }
                _minio_client.set_bucket_policy(
                    settings.MINIO_BUCKET_NAME,
                    json.dumps(policy)
                )
                logger.info(f"Set public read policy for bucket: {settings.MINIO_BUCKET_NAME}")
            except Exception as e:
                logger.warning(f"Could not set bucket policy (may need manual configuration): {e}")
        except S3Error as e:
            logger.error(f"Error checking/creating MinIO bucket: {e}")
            raise
    
    return _minio_client


async def upload_image_to_minio(
    image_data: bytes,
    filename: str,
    content_type: str = "image/jpeg"
) -> Optional[str]:
    """
    Upload image to MinIO and return public URL.
    
    Args:
        image_data: Image binary data
        filename: Filename for the image (will be stored as this)
        content_type: MIME type of the image
        
    Returns:
        Public URL of the uploaded image, or None if upload failed
    """
    try:
        client = get_minio_client()
        
        # Upload image
        image_stream = io.BytesIO(image_data)
        client.put_object(
            settings.MINIO_BUCKET_NAME,
            filename,
            image_stream,
            length=len(image_data),
            content_type=content_type
        )
        
        # Generate public URL using MINIO_PUBLIC_URL
        # Remove trailing slash if present
        public_base_url = settings.MINIO_PUBLIC_URL.rstrip('/')
        public_url = f"{public_base_url}/{settings.MINIO_BUCKET_NAME}/{filename}"
        
        logger.info(f"Successfully uploaded image to MinIO: {filename}, public URL: {public_url}")
        return public_url
        
    except S3Error as e:
        logger.error(f"Error uploading image to MinIO: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading image to MinIO: {e}", exc_info=True)
        return None


async def download_telegram_file(bot, file_id: str) -> Optional[bytes]:
    """
    Download file from Telegram by file_id.
    
    Args:
        bot: Bot instance
        file_id: Telegram file_id
        
    Returns:
        File binary data, or None if download failed
    """
    try:
        file = await bot.get_file(file_id)
        file_data = await bot.download_file(file.file_path)
        return file_data.read()
    except Exception as e:
        logger.error(f"Error downloading Telegram file {file_id}: {e}")
        return None


async def upload_telegram_photo_to_minio(
    bot,
    file_id: str,
    user_id: int
) -> Optional[str]:
    """
    Download photo from Telegram and upload to MinIO.
    
    Args:
        bot: Bot instance
        file_id: Telegram file_id
        user_id: User ID for generating unique filename
        
    Returns:
        Public URL of the uploaded image, or None if upload failed
    """
    try:
        # Download file from Telegram
        file_data = await download_telegram_file(bot, file_id)
        if not file_data:
            logger.error(f"Failed to download file {file_id} from Telegram")
            return None
        
        # Generate unique filename
        import hashlib
        import time
        timestamp = int(time.time())
        file_hash = hashlib.md5(f"{user_id}_{timestamp}_{file_id}".encode()).hexdigest()[:12]
        filename = f"profile_{user_id}_{file_hash}.jpg"
        
        # Upload to MinIO
        url = await upload_image_to_minio(file_data, filename, "image/jpeg")
        return url
        
    except Exception as e:
        logger.error(f"Error uploading Telegram photo to MinIO: {e}", exc_info=True)
        return None


def delete_image_from_minio(filename: str) -> bool:
    """
    Delete image from MinIO.
    
    Args:
        filename: Filename to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        client = get_minio_client()
        client.remove_object(settings.MINIO_BUCKET_NAME, filename)
        logger.info(f"Successfully deleted image from MinIO: {filename}")
        return True
    except S3Error as e:
        logger.error(f"Error deleting image from MinIO: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting image from MinIO: {e}", exc_info=True)
        return False


def is_url_accessible_from_internet(url: str) -> bool:
    """
    Check if URL is accessible from internet (not localhost).
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is HTTPS and not localhost, False otherwise
    """
    if not url:
        return False
    
    # Must be HTTPS for Telegram
    if not url.startswith('https://'):
        return False
    
    # Check if it's localhost or internal IP
    url_lower = url.lower()
    if any(blocked in url_lower for blocked in ['localhost', '127.0.0.1', '0.0.0.0', '::1', 'minio:']):
        return False
    
    # Check if it's a Docker internal network
    if ':9000' in url or ':9001' in url:
        # If it's using internal Docker network, it's not accessible
        if 'minio:' in url_lower or 'localhost' in url_lower:
            return False
    
    return True


def get_telegram_thumbnail_url(url: str) -> Optional[str]:
    """
    Get thumbnail URL for Telegram inline query.
    Only returns URL if it's accessible from internet.
    
    Args:
        url: Image URL (MinIO or Telegram file_id)
        
    Returns:
        URL if accessible, None otherwise
    """
    if not url:
        return None
    
    # If it's already an HTTPS URL and accessible, use it
    if url.startswith('https://') and is_url_accessible_from_internet(url):
        return url
    
    # If it's HTTP, don't use it (Telegram requires HTTPS for thumbnails)
    if url.startswith('http://'):
        return None
    
    # If it's a file_id, we can't use it directly as thumbnail
    # Telegram will handle it automatically if we don't provide thumbnail_url
    return None

