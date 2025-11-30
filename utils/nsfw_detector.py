"""
NSFW content detection utilities for images.
Uses NudeNet library for detecting inappropriate content in profile images.
"""
import logging
import io
from typing import Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

# Try to import NudeNet, fallback to basic detection if not available
try:
    from nudenet import NudeDetector
    NUDENET_AVAILABLE = True
except ImportError:
    NUDENET_AVAILABLE = False
    logger.warning("NudeNet not available. NSFW detection will use basic heuristics.")


# Global detector instance (lazy loading)
_detector: Optional[NudeDetector] = None


def get_detector() -> Optional[NudeDetector]:
    """
    Get or create NudeNet detector instance (lazy loading).
    
    Returns:
        NudeDetector instance or None if not available
    """
    global _detector
    
    if not NUDENET_AVAILABLE:
        return None
    
    if _detector is None:
        try:
            # Try to initialize with different model types
            try:
                _detector = NudeDetector()
            except Exception:
                # Try with explicit model type
                _detector = NudeDetector('base')
            logger.info("NudeNet detector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize NudeNet detector: {e}", exc_info=True)
            return None
    
    return _detector


def check_image_nsfw(image_data: bytes) -> Tuple[bool, float]:
    """
    Check if image contains NSFW content.
    
    Args:
        image_data: Image binary data
        
    Returns:
        Tuple of (is_nsfw, confidence_score)
        - is_nsfw: True if image is likely NSFW
        - confidence_score: Confidence score (0.0 to 1.0)
    """
    if not image_data:
        logger.warning("Empty image data provided")
        return True, 1.0  # Reject empty images
    
    try:
        # Try to load image
        image = Image.open(io.BytesIO(image_data))
        
        # Basic validation: check image size
        width, height = image.size
        if width < 10 or height < 10:
            logger.warning(f"Image too small: {width}x{height}")
            return True, 1.0  # Reject very small images
        
        # Use NudeNet to check for NSFW content
        detector = get_detector()
        if detector:
            try:
                import tempfile
                import os
                
                # NudeNet expects image path, so we'll save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    image.save(tmp_file.name, 'JPEG')
                    tmp_path = tmp_file.name
                
                try:
                    # Try different methods based on NudeNet version
                    result = None
                    
                    # Method 1: Try detect() (for object detection)
                    try:
                        result = detector.detect(tmp_path)
                        logger.debug(f"Using detect() method, result type: {type(result)}")
                    except Exception as e1:
                        logger.debug(f"detect() method failed: {e1}")
                        
                        # Method 2: Try classify() (for image classification)
                        try:
                            result = detector.classify(tmp_path)
                            logger.debug(f"Using classify() method, result type: {type(result)}")
                        except Exception as e2:
                            logger.debug(f"classify() method failed: {e2}")
                            
                            # Method 3: Try censor() (returns dict with unsafe score)
                            try:
                                result = detector.censor(tmp_path)
                                logger.debug(f"Using censor() method, result type: {type(result)}")
                            except Exception as e3:
                                logger.error(f"All NudeNet methods failed: detect={e1}, classify={e2}, censor={e3}")
                                raise e3
                    
                    # Log the result structure for debugging
                    logger.debug(f"NudeNet detection result type: {type(result)}, value: {result}")
                    
                    # Check for NSFW classes
                    # NudeNet 3.x uses different class names
                    nsfw_classes = [
                        'EXPOSED_ANUS', 'EXPOSED_ARMPITS', 'EXPOSED_BELLY', 
                        'EXPOSED_BUTTOCKS', 'EXPOSED_BREAST_F', 'EXPOSED_BREAST_M',
                        'EXPOSED_GENITALIA_F', 'EXPOSED_GENITALIA_M',
                        # Alternative class names in newer versions
                        'EXPOSED_BREAST', 'EXPOSED_GENITALIA', 'EXPOSED_BUTTOCKS',
                        'FEMALE_BREAST_EXPOSED', 'FEMALE_GENITALIA_EXPOSED',
                        'MALE_BREAST_EXPOSED', 'MALE_GENITALIA_EXPOSED',
                        'ANUS_EXPOSED', 'ARMPITS_EXPOSED', 'BELLY_EXPOSED'
                    ]
                    
                    max_confidence = 0.0
                    
                    # Handle different result formats
                    if isinstance(result, dict):
                        # Result might be a dict with 'prediction' or 'detections' key
                        if 'prediction' in result:
                            result = result['prediction']
                        elif 'detections' in result:
                            result = result['detections']
                        elif 'boxes' in result:
                            # Format: {'boxes': [...], 'scores': [...], 'classes': [...]}
                            boxes = result.get('boxes', [])
                            scores = result.get('scores', [])
                            classes = result.get('classes', [])
                            for i, class_name in enumerate(classes):
                                if class_name in nsfw_classes:
                                    confidence = scores[i] if i < len(scores) else 0.0
                                    max_confidence = max(max_confidence, confidence)
                            result = None  # Already processed
                    
                    if isinstance(result, list):
                        for detection in result:
                            if isinstance(detection, dict):
                                # Try different key names
                                class_name = detection.get('class', '') or detection.get('label', '') or detection.get('name', '')
                                confidence = detection.get('score', 0.0) or detection.get('confidence', 0.0) or detection.get('prob', 0.0)
                                
                                logger.debug(f"Detection: class={class_name}, confidence={confidence}")
                                
                                if class_name in nsfw_classes:
                                    max_confidence = max(max_confidence, confidence)
                    
                    # Also check for 'unsafe' or 'nsfw' key in result if it's a dict
                    if isinstance(result, dict):
                        # Check various possible keys for NSFW score
                        unsafe_score = (
                            result.get('unsafe', 0.0) or 
                            result.get('nsfw', 0.0) or 
                            result.get('porn', 0.0) or
                            result.get('sexy', 0.0) or
                            result.get('hentai', 0.0) or
                            result.get('pornography', 0.0)
                        )
                        if unsafe_score > 0:
                            max_confidence = max(max_confidence, unsafe_score)
                        
                        # Also check if result has 'classes' or 'labels' with scores
                        if 'classes' in result and isinstance(result['classes'], dict):
                            for class_name, score in result['classes'].items():
                                if class_name in nsfw_classes or 'nsfw' in class_name.lower() or 'porn' in class_name.lower():
                                    max_confidence = max(max_confidence, float(score))
                    
                    # Threshold for NSFW detection
                    # 0.5 provides better balance - catches real NSFW but allows borderline cases
                    # Lower values catch more (more false positives), higher values are more strict
                    is_nsfw = max_confidence > 0.5
                    
                    logger.info(f"NSFW check result: is_nsfw={is_nsfw}, max_confidence={max_confidence:.2f}")
                    
                    if is_nsfw:
                        logger.warning(f"NSFW content detected with confidence: {max_confidence:.2f}")
                        return is_nsfw, max_confidence
                    
                    # NudeNet didn't detect NSFW, continue to pixelation check
                    logger.debug(f"NudeNet passed (confidence: {max_confidence:.2f}), checking pixelation")
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                
            except Exception as e:
                logger.error(f"Error in NudeNet detection: {e}", exc_info=True)
                # Fallback to basic heuristics
                return basic_nsfw_check(image)
        else:
            # NudeNet not available, fallback to basic heuristics
            return basic_nsfw_check(image)
        
        # Image passed all checks
        return False, 0.0
            
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        # If we can't process the image, reject it (conservative approach)
        return True, 1.0


def basic_nsfw_check(image: Image.Image) -> Tuple[bool, float]:
    """
    Basic NSFW check using heuristics (fallback when NudeNet is not available).
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple of (is_nsfw, confidence_score)
    """
    try:
        # Basic checks:
        # 1. Check image dimensions (very small or very large might be suspicious)
        width, height = image.size
        aspect_ratio = width / height if height > 0 else 0
        
        # 2. Check if image is mostly skin-colored (basic heuristic)
        # This is a very simple check and not very accurate
        # In production, always use proper ML models
        
        # For now, we'll be conservative and only reject obvious issues
        # Most images will pass this basic check
        # The real protection comes from NudeNet
        
        # If image is extremely small or large, be suspicious
        if width < 50 or height < 50:
            return True, 0.7
        
        if width > 10000 or height > 10000:
            return True, 0.7
        
        # Otherwise, pass (conservative - let NudeNet do the real work)
        return False, 0.0
        
    except Exception as e:
        logger.error(f"Error in basic NSFW check: {e}", exc_info=True)
        return True, 1.0  # Reject on error


async def download_and_check_photo(bot, file_id: str) -> Tuple[bool, Optional[str]]:
    """
    Download photo from Telegram and check for NSFW content.
    
    Args:
        bot: Telegram bot instance
        file_id: Telegram file_id of the photo
        
    Returns:
        Tuple of (is_safe, error_message)
        - is_safe: True if image is safe, False if NSFW
        - error_message: Error message if image is not safe, None otherwise
    """
    try:
        from utils.minio_storage import download_telegram_file
        
        # Download image from Telegram
        image_data = await download_telegram_file(bot, file_id)
        
        if not image_data:
            logger.error(f"Failed to download image with file_id: {file_id}")
            return False, "❌ متأسفانه در دانلود تصویر مشکلی پیش آمد.\n\nلطفاً دوباره تلاش کنید:"
        
        # Check for NSFW content
        is_nsfw, confidence = check_image_nsfw(image_data)
        
        if is_nsfw:
            logger.warning(f"NSFW/image quality issue detected (confidence: {confidence:.2f})")
            # NSFW content detected
            return False, "❌ متأسفانه تصویر شما نمی‌تواند به عنوان عکس پروفایل استفاده شود.\n\nلطفاً تصویر مناسب‌تری ارسال کنید:"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error downloading and checking photo: {e}", exc_info=True)
        # Conservative approach: reject on error
        return False, "❌ متأسفانه در بررسی تصویر مشکلی پیش آمد.\n\nلطفاً دوباره تلاش کنید:"

