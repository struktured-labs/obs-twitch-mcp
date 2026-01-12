"""
Image processing utilities for translation service.

Provides functions for perceptual hashing, cropping, format conversion,
and debugging for the background translation service.
"""

import io
from pathlib import Path

import imagehash
from PIL import Image


def compute_perceptual_hash(image: Image.Image) -> imagehash.ImageHash:
    """
    Compute perceptual hash of an image using pHash algorithm.

    Perceptual hashing creates a fingerprint of the visual content that is:
    - Robust to minor changes (compression, slight color shifts)
    - Fast to compute (<10ms)
    - Easy to compare (hamming distance)

    Args:
        image: PIL Image to hash

    Returns:
        ImageHash object that can be compared with other hashes
    """
    return imagehash.phash(image)


def crop_image(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """
    Crop image to specified bounding box.

    Args:
        image: PIL Image to crop
        box: Bounding box as (x, y, width, height)

    Returns:
        Cropped PIL Image
    """
    x, y, width, height = box
    return image.crop((x, y, x + width, y + height))


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """
    Convert PIL Image to bytes in specified format.

    Args:
        image: PIL Image to convert
        format: Output format (PNG, JPEG, etc.)

    Returns:
        Image data as bytes
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def bytes_to_image(data: bytes) -> Image.Image:
    """
    Convert bytes to PIL Image.

    Args:
        data: Image data as bytes

    Returns:
        PIL Image object
    """
    return Image.open(io.BytesIO(data))


def compare_hashes(hash1: imagehash.ImageHash, hash2: imagehash.ImageHash) -> int:
    """
    Compare two perceptual hashes using hamming distance.

    Hamming distance is the number of bits that differ between the two hashes.
    Lower values mean more similar images:
    - 0-5: Nearly identical
    - 5-10: Very similar (likely same dialogue)
    - 10-20: Similar but noticeable changes
    - 20+: Different images

    Args:
        hash1: First ImageHash
        hash2: Second ImageHash

    Returns:
        Hamming distance (number of differing bits)
    """
    return hash1 - hash2


def save_debug_image(image: Image.Image, path: Path, label: str) -> None:
    """
    Save image for debugging purposes.

    Creates parent directories if needed. Useful for inspecting
    cropped regions, dialogue box detection, etc.

    Args:
        image: PIL Image to save
        path: Directory to save to
        label: Descriptive filename (e.g., "dialogue_crop_001")
    """
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / f"{label}.png"
    image.save(filepath)
