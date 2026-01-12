"""
OCR client for Japanese game text extraction.

Uses manga-ocr (specialized for pixelated Japanese text in games/manga)
for accurate local OCR without API costs.
"""

import logging
import re
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


def _is_valid_japanese_text(text: str) -> bool:
    """
    Validate if OCR result is likely real Japanese text (not hallucination).

    manga-ocr has no confidence scores and will hallucinate text from noise.
    This filters out obvious garbage.

    Args:
        text: OCR result to validate

    Returns:
        True if text appears to be valid Japanese, False if likely hallucination
    """
    if not text or not text.strip():
        return False

    text = text.strip()

    # Minimum length (too short is likely noise)
    if len(text) < 3:
        logger.debug(f"Rejected: too short ({len(text)} chars): {text}")
        return False

    # Count Japanese characters (hiragana, katakana, kanji)
    hiragana = re.findall(r'[\u3040-\u309F]', text)  # ぁ-ん
    katakana = re.findall(r'[\u30A0-\u30FF]', text)  # ァ-ヶ
    kanji = re.findall(r'[\u4E00-\u9FFF]', text)     # CJK unified ideographs

    japanese_chars = len(hiragana) + len(katakana) + len(kanji)
    total_chars = len(text)

    # At least 50% must be Japanese characters
    if japanese_chars < total_chars * 0.5:
        logger.debug(
            f"Rejected: only {japanese_chars}/{total_chars} Japanese chars: {text}"
        )
        return False

    # Reject if mostly repetitive (e.g., "ののののの")
    if len(set(text)) < len(text) * 0.3:
        logger.debug(f"Rejected: too repetitive: {text}")
        return False

    logger.debug(f"Accepted: {japanese_chars}/{total_chars} Japanese chars: {text}")
    return True


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
            Extracted Japanese text as string (empty if no valid text found)

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

            logger.debug(f"OCR raw result: {text[:100]}...")

            # Validate result (filter hallucinations from background noise)
            if not _is_valid_japanese_text(text):
                logger.info(f"OCR result rejected as hallucination: {text[:50]}...")
                return ""

            logger.info(f"OCR accepted: {text}")
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
