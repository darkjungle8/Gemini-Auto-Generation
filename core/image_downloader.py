import os
import base64
import logging
from io import BytesIO

import requests
from PIL import Image

logger = logging.getLogger(__name__)


class ImageDownloader:
    """Handles downloading and converting images to JPG format."""

    @staticmethod
    def download_and_save_as_jpg(image_data, output_path, quality=95):
        """Save image data (base64, URL, or bytes) as a JPG file.

        Args:
            image_data: Can be a data URI string, HTTP URL, raw base64, or bytes.
            output_path: Absolute path where the JPG should be saved.
            quality: JPEG quality (1-100).

        Returns:
            The output_path on success.
        """
        image_bytes = ImageDownloader._resolve_image_data(image_data)
        img = Image.open(BytesIO(image_bytes))

        # Convert to RGB if needed (e.g., RGBA or palette mode)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "JPEG", quality=quality)
        logger.info(f"Saved image: {output_path} ({img.size[0]}x{img.size[1]})")
        return output_path

    @staticmethod
    def download_with_cookies(url, cookies, output_path, quality=95):
        """Download image using browser cookies for authentication."""
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
            )
        resp = session.get(url, timeout=60)
        if resp.status_code == 200:
            return ImageDownloader.download_and_save_as_jpg(
                resp.content, output_path, quality
            )
        raise Exception(f"Download failed with HTTP {resp.status_code}")

    @staticmethod
    def _resolve_image_data(image_data):
        """Convert various image data formats to raw bytes."""
        if isinstance(image_data, bytes):
            return image_data

        if not isinstance(image_data, str):
            raise ValueError(f"Unsupported image data type: {type(image_data)}")

        # data URI (e.g. 'data:image/png;base64,...')
        if image_data.startswith("data:"):
            _, data = image_data.split(",", 1)
            return base64.b64decode(data)

        # HTTP(S) URL
        if image_data.startswith("http"):
            resp = requests.get(image_data, timeout=60)
            resp.raise_for_status()
            return resp.content

        # Assume raw base64
        return base64.b64decode(image_data)
