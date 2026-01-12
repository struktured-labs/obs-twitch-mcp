"""
OCR client for Japanese game text extraction.

Uses manga-ocr (specialized for pixelated Japanese text in games/manga)
for accurate local OCR without API costs.
"""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Global singleton instance
_ocr_instance: Optional["MangaOCR"] = None


def get_ocr_client():
    """
    Get or create global manga-ocr instance.

    Lazy-loads the model on first use (takes ~2-3 seconds).
    Subsequent calls return the cached instance.

    Returns:
        MangaOCR instance
    """
    global _ocr_instance

    if _ocr_instance is None:
        logger.info("Loading manga-ocr model (first use, ~2-3 seconds)...")
        try:
            from manga_ocr import MangaOcr

            _ocr_instance = MangaOcr()
            logger.info("manga-ocr model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load manga-ocr: {e}", exc_info=True)
            raise

    return _ocr_instance


class OCRClient:
    """
    Client for extracting Japanese text from game screenshots.

    Uses manga-ocr (based on Transformers) for accurate OCR of pixelated text.
    """

    def __init__(self):
        """Initialize OCR client (lazy-loads model on first use)."""
        self.ocr = None

    def extract_text(self, image: Image.Image) -> str:
        """
        Extract Japanese text from image using manga-ocr.

        Args:
            image: PIL Image to extract text from

        Returns:
            Extracted Japanese text as string (empty if no text found)

        Raises:
            Exception: If OCR fails
        """
        if self.ocr is None:
            self.ocr = get_ocr_client()

        try:
            # manga-ocr expects PIL Image
            text = self.ocr(image)

            # Clean up text (remove extra whitespace, normalize)
            text = text.strip()

            logger.debug(f"OCR extracted: {text[:100]}...")
            return text

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            raise

    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        """
        Extract Japanese text from image bytes.

        Args:
            image_bytes: Image data as bytes

        Returns:
            Extracted Japanese text as string

        Raises:
            Exception: If OCR fails
        """
        from io import BytesIO

        image = Image.open(BytesIO(image_bytes))
        return self.extract_text(image)
