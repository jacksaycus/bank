import io
from typing import Tuple

from PIL import Image, UnidentifiedImageError

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()

def validate_image(file_data: bytes) -> Tuple[bool, str]:
    try:
        file_size_mb = len(file_data) / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE / (1024 * 1024):
            return (
                False,
                f"File size exceeds {settings.MAX_FILE_SIZE/1024*1024}MB limit",
            )
        
        image_buffer = io.BytesIO(file_data)

        with Image.open(image_buffer) as img:
            if img.format is None or img.format.lower() not in ["jpeg", "png", "jpg"]:
                return False, "Invalid image format. Only JPEG, and PNG are allowed"
            
            width, height = img.size
            if width > settings.MAX_DIMENSION or height > settings.MAX_DIMENSION:
                return (
                    False,
                    f"Image dinmensions exceed {settings.MAX_DIMENSION}px limit",
                )
            
            try:
                img.load()
            except Exception as e:
                return (False, f"Invalid or corrupted image file: {str(e)}")
            return True, "Image is valid"
        
    except UnidentifiedImageError:
        return False, "File is not a valid image"
    
    except Exception as e:
        logger.error(f"Image validation error: {str(e)}")
        return False, f"Invalid image file: {str(e)}"
    