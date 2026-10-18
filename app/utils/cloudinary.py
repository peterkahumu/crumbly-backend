import cloudinary
import cloudinary.uploader

from app.config import get_settings

settings = get_settings()

if settings.cloudinary_cloud_name:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )


async def upload_image(file_bytes: bytes) -> str:
    """Uploads an image to Cloudinary and returns the secure URL."""
    result = cloudinary.uploader.upload(file_bytes, folder="crumbly")
    return result["secure_url"]
