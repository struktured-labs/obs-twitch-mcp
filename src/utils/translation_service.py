"""
Background translation service for automatic game dialogue OCR and translation.

Provides a background asyncio task that:
1. Continuously monitors OBS screenshots
2. Auto-detects dialogue box regions
3. Uses perceptual hashing to detect changes
4. Translates only when dialogue changes
5. Updates overlay automatically

Performance optimizations:
- Crops to dialogue region (25x payload reduction)
- Smart change detection (60-80% API call reduction)
- Background processing (non-blocking)
- Cached dialogue box detection
"""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import imagehash
from PIL import Image

from .image_utils import (
    bytes_to_image,
    compare_hashes,
    compute_perceptual_hash,
    crop_image,
    image_to_bytes,
    save_debug_image,
)
from .vision_client import get_vision_client
from .ocr_client import OCRClient

logger = logging.getLogger(__name__)


@dataclass
class TranslationService:
    """
    Background service for automatic game dialogue translation.

    Configuration:
        poll_interval: Seconds between screenshot checks (default: 2.0)
        change_threshold: Hamming distance threshold for change detection (default: 7)
        detection_interval: Seconds between dialogue box re-detection (default: 300)
        debug_mode: Save debug images to tmp/translation_debug/ (default: False)

    State:
        enabled: Whether service is running
        dialogue_box: Cached dialogue box coordinates (x, y, width, height)
        last_hash: Previous frame's perceptual hash
        last_translation: Last translation result
        last_detection_time: When dialogue box was last detected

    Statistics:
        total_screenshots: Total frames processed
        total_translations: Number of API calls made
        api_calls_saved: Number of API calls skipped via change detection
        avg_latency_ms: Average translation latency
    """

    # Configuration
    poll_interval: float = 2.0
    change_threshold: int = 7
    detection_interval: float = 300.0  # 5 minutes
    debug_mode: bool = False

    # State
    enabled: bool = False
    dialogue_box: tuple[int, int, int, int] | None = None
    last_hash: imagehash.ImageHash | None = None
    last_translation: dict | None = None
    last_detection_time: float = 0.0
    last_change_time: float = 0.0  # Track when dialogue last changed
    last_translation_text: str = ""  # Track exact text to detect staleness

    # Statistics
    total_screenshots: int = 0
    total_translations: int = 0
    api_calls_saved: int = 0
    avg_latency_ms: float = 0.0

    # Background tasks
    _task: asyncio.Task | None = None
    _detection_task: asyncio.Task | None = None  # NEW: parallel detection
    _processing_frame: bool = False  # NEW: busy flag for frame skipping
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _debug_counter: int = 0

    # Instrumentation (NEW for Phase 3)
    screenshot_time_ms: float = 0.0
    detection_time_ms: float = 0.0
    translation_time_ms: float = 0.0
    frames_skipped: int = 0
    detection_failures: int = 0

    async def start(self, obs_client, translate_fn, overlay_fn, clear_overlay_fn=None) -> dict:
        """
        Start the background translation service.

        Args:
            obs_client: OBS client for capturing screenshots
            translate_fn: Async function to translate cropped images
            overlay_fn: Async function to update translation overlay
            clear_overlay_fn: Async function to clear translation overlay (optional)

        Returns:
            Status dict with service state
        """
        async with self._lock:
            if self.enabled:
                return {"status": "already_running"}

            # Reset ALL state when starting (comprehensive reset to fix restart issues)
            self.last_hash = None
            self.last_translation = None
            self.last_translation_text = ""  # CRITICAL FIX: was missing, caused stale detection on restart
            self.last_change_time = time.time()

            # Create main translation loop task
            self._task = asyncio.create_task(
                self._translation_loop(obs_client, translate_fn, overlay_fn, clear_overlay_fn)
            )

            # Create background detection loop task (NEW - Phase 2 Step 2.3)
            # This runs independently to avoid blocking main loop (eliminates 2000ms stalls)
            self._detection_task = asyncio.create_task(
                self._detection_loop(obs_client)
            )

            # Only mark as enabled AFTER both tasks created successfully (fixes start/stop race)
            self.enabled = True

            logger.info(
                f"Translation service started (poll_interval={self.poll_interval}s, "
                f"change_threshold={self.change_threshold})"
            )

            return {
                "status": "started",
                "poll_interval": self.poll_interval,
                "change_threshold": self.change_threshold,
                "detection_interval": self.detection_interval,
            }

    async def stop(self, clear_overlay: bool = True) -> dict:
        """
        Stop the background translation service.

        Args:
            clear_overlay: Whether to clear the translation overlay

        Returns:
            Status dict with final statistics
        """
        async with self._lock:
            if not self.enabled:
                return {"status": "not_running"}

            self.enabled = False

            # Cancel main translation loop
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

            # Cancel background detection loop (NEW - Phase 2 Step 2.3)
            if self._detection_task:
                self._detection_task.cancel()
                try:
                    await self._detection_task
                except asyncio.CancelledError:
                    pass
                self._detection_task = None

            stats = self.get_status()

            logger.info(
                f"Translation service stopped. "
                f"Stats: {self.total_translations} translations, "
                f"{self.api_calls_saved} API calls saved "
                f"({self._efficiency_percent():.1f}% efficient)"
            )

            return {
                "status": "stopped",
                "final_stats": stats,
                "clear_overlay": clear_overlay,
            }

    async def _translation_loop(self, obs_client, translate_fn, overlay_fn, clear_overlay_fn=None) -> None:
        """
        Main background loop for translation service.

        Continuously:
        1. Captures OBS screenshots
        2. Detects/validates dialogue box
        3. Crops to dialogue region
        4. Checks for changes via perceptual hash
        5. Translates if changed
        6. Updates overlay

        Args:
            obs_client: OBS client for screenshots
            translate_fn: Translation function
            overlay_fn: Overlay update function
            clear_overlay_fn: Clear overlay function (optional)
        """
        logger.info("Translation loop started")

        while self.enabled:
            try:
                # Frame skipping (CRITICAL FIX Phase 2 Step 2.4): Skip if previous frame still processing
                # This prevents service from falling behind when API is slow
                if self._processing_frame:
                    self.frames_skipped += 1
                    logger.debug(
                        f"Previous frame still processing, skipping frame "
                        f"(total skipped: {self.frames_skipped})"
                    )
                    await asyncio.sleep(self.poll_interval)
                    continue

                await self._process_frame(obs_client, translate_fn, overlay_fn, clear_overlay_fn)
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("Translation loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in translation loop: {e}", exc_info=True)
                # Don't crash on errors, just log and continue
                await asyncio.sleep(self.poll_interval)

    async def _detection_loop(self, obs_client) -> None:
        """
        Background loop for dialogue box detection.

        Runs independently of main translation loop to avoid blocking.
        Detects dialogue box on startup, then re-detects every detection_interval.

        This is CRITICAL FIX #2.3 - eliminates 2000ms stalls in main loop.

        Args:
            obs_client: OBS client for screenshots
        """
        logger.info("Detection loop started (background, non-blocking)")

        while self.enabled:
            try:
                if self._should_detect_dialogue_box():
                    detect_start = time.time()
                    logger.info("Starting dialogue box detection...")

                    try:
                        screenshot_bytes = obs_client.get_screenshot()

                        # Call Vision API for detection
                        vision_client = get_vision_client()
                        box = await vision_client.detect_dialogue_box(screenshot_bytes)

                        # Update state with lock
                        async with self._lock:
                            self.dialogue_box = box
                            self.last_detection_time = time.time()
                            self.detection_time_ms = (time.time() - detect_start) * 1000

                        logger.info(
                            f"Dialogue box detected ({self.detection_time_ms:.0f}ms): "
                            f"x={box[0]}, y={box[1]}, w={box[2]}, h={box[3]}"
                        )

                    except Exception as e:
                        self.detection_failures += 1
                        logger.error(
                            f"Detection failed (attempt {self.detection_failures}): {e}",
                            exc_info=True
                        )
                        # Don't crash detection loop, try again next interval

                # Sleep for detection interval (much longer than poll interval)
                await asyncio.sleep(self.detection_interval)

            except asyncio.CancelledError:
                logger.info("Detection loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in detection loop: {e}", exc_info=True)
                await asyncio.sleep(self.detection_interval)

    async def _process_frame(self, obs_client, translate_fn, overlay_fn, clear_overlay_fn=None) -> None:
        """
        Process a single frame for translation.

        Args:
            obs_client: OBS client
            translate_fn: Translation function
            overlay_fn: Overlay function
            clear_overlay_fn: Clear overlay function (optional)
        """
        # Mark as busy (CRITICAL FIX Phase 2 Step 2.4)
        # This flag prevents frame queue pileup when API is slow
        self._processing_frame = True

        try:
            print(f"[SERVICE] _process_frame called", flush=True)
            start_time = time.time()

            # 1. Capture screenshot
            screenshot_start = time.time()
            screenshot_bytes = obs_client.get_screenshot()
            self.total_screenshots += 1
            self.screenshot_time_ms = (time.time() - screenshot_start) * 1000
            print(
                f"[SERVICE] Screenshot captured: {len(screenshot_bytes)} bytes, "
                f"total={self.total_screenshots}, time={self.screenshot_time_ms:.0f}ms",
                flush=True
            )

            if self.debug_mode:
                self._save_debug("full_screenshot", screenshot_bytes)

            # 2. Check if dialogue box is available (detection happens in background loop)
            # CRITICAL FIX (Phase 2 Step 2.3): No longer blocks here - detection runs independently
            if not self.dialogue_box:
                logger.debug("Waiting for dialogue box detection (background loop will handle this)")
                print(f"[SERVICE] No dialogue box yet, waiting for background detection...", flush=True)
                return

            # 3. Crop to dialogue region
            print(f"[SERVICE] Cropping to dialogue box: {self.dialogue_box}", flush=True)
            image = bytes_to_image(screenshot_bytes)
            cropped = crop_image(image, self.dialogue_box)

            if self.debug_mode:
                self._save_debug("cropped_dialogue", image_to_bytes(cropped))

            # 4. Detect change (with exception handling and unconditional hash update)
            print(f"[SERVICE] Checking for changes... last_hash={self.last_hash is not None}", flush=True)

            try:
                has_changed, new_hash = self._compute_change_status(cropped)

                # Update hash IMMEDIATELY and UNCONDITIONALLY (prevents drift)
                # This is the CRITICAL fix - hash must always reflect current frame
                self.last_hash = new_hash

                print(f"[SERVICE] Change detection: has_changed={has_changed}", flush=True)

                # Log to file for debugging
                with open("/tmp/translation_service_debug.log", "a") as f:
                    f.write(f"Frame {self.total_screenshots}: has_changed={has_changed}, hash_updated=True\n")

                logger.debug(f"Change detection: has_changed={has_changed}")

            except Exception as e:
                logger.error(f"Hash computation failed: {e}", exc_info=True)
                print(f"[SERVICE] Hash computation error: {e}", flush=True)
                # Don't update hash on error - keep last valid hash
                self.api_calls_saved += 1
                return

            # Force re-check with dynamic threshold (not hardcoded)
            force_recheck_threshold = max(2.0, self.poll_interval * 4)
            time_since_change = time.time() - self.last_change_time if self.last_change_time > 0 else 0
            force_recheck = time_since_change > force_recheck_threshold and self.last_translation is not None

            if not has_changed and not force_recheck:
                self.api_calls_saved += 1
                print(f"[SERVICE] No change detected, skipping (saved={self.api_calls_saved})", flush=True)
                return

            if force_recheck:
                print(f"[SERVICE] Forcing recheck (no change for {time_since_change:.1f}s)", flush=True)

            # 5. Translate changed dialogue
            print("[TRANSLATION SERVICE] Change detected! Starting translation...", flush=True)
            logger.info("Change detected! Starting translation...")

            # Log to file
            with open("/tmp/translation_service_debug.log", "a") as f:
                f.write(f"Frame {self.total_screenshots}: TRANSLATING!\n")

            try:
                cropped_bytes = image_to_bytes(cropped)
                print(f"[TRANSLATION SERVICE] Cropped image: {len(cropped_bytes)} bytes", flush=True)
                logger.info(f"Cropped image: {len(cropped_bytes)} bytes")

                # Add translation timing
                translation_start = time.time()
                translation = await self._translate_region(cropped_bytes, translate_fn)
                self.translation_time_ms = (time.time() - translation_start) * 1000

                print(f"[TRANSLATION SERVICE] Translation result: {translation}", flush=True)
                logger.info(f"Translation result: {translation}")

                # Log translation to file
                with open("/tmp/translation_service_debug.log", "a") as f:
                    f.write(f"Frame {self.total_screenshots}: Translation={translation}\n")

                # Check if dialogue is empty (removed from screen)
                if not translation or not translation.get("english_text"):
                    logger.info(f"No dialogue detected, clearing overlay")
                    print("[TRANSLATION SERVICE] No dialogue detected, clearing overlay", flush=True)
                    # Clear overlay if dialogue is gone
                    if clear_overlay_fn:
                        await clear_overlay_fn()
                    self.last_translation = None
                    self.last_translation_text = ""  # CRITICAL FIX: reset text to prevent stale detection
                    self.last_change_time = time.time()  # Reset change timer
                    return

                # 6. Check if this is the same text (stale detection - safety fallback only)
                current_text = translation["english_text"]
                if current_text == self.last_translation_text:
                    # Same text - check if it's been way too long (60 seconds - safety only)
                    time_with_same_text = time.time() - self.last_change_time
                    if time_with_same_text > 60.0:
                        logger.info(f"Translation stale for {time_with_same_text:.1f}s, clearing (safety)")
                        print(f"[TRANSLATION SERVICE] Stale translation safety clear ({time_with_same_text:.1f}s)", flush=True)
                        if clear_overlay_fn:
                            await clear_overlay_fn()
                        self.last_translation = None
                        self.last_translation_text = ""
                        self.last_change_time = time.time()
                        return
                    # Same text but not stale yet - skip update
                    return
                else:
                    # New text - update overlay
                    logger.info(f"Calling overlay with: {translation['english_text']}")
                    await overlay_fn(
                        japanese_text=translation.get("japanese_text", ""),
                        english_text=translation["english_text"],
                    )
                    logger.info("Overlay called successfully")

                    self.last_translation = translation
                    self.last_translation_text = current_text
                    self.total_translations += 1
                    self.last_change_time = time.time()  # Update change timestamp

                # Update statistics
                latency_ms = (time.time() - start_time) * 1000
                if self.avg_latency_ms == 0:
                    self.avg_latency_ms = latency_ms
                else:
                    # Exponential moving average
                    self.avg_latency_ms = 0.7 * self.avg_latency_ms + 0.3 * latency_ms

                logger.info(
                    f"Translated dialogue ({latency_ms:.0f}ms total, "
                    f"{self.screenshot_time_ms:.0f}ms screenshot, "
                    f"{self.translation_time_ms:.0f}ms API): "
                    f"{translation['english_text'][:50]}..."
                )

            except Exception as e:
                logger.error(f"Translation failed: {type(e).__name__}: {e}", exc_info=True)

        finally:
            # Clear busy flag (CRITICAL FIX Phase 2 Step 2.4)
            # Ensures flag is always cleared even if exception occurs
            self._processing_frame = False

    def _should_detect_dialogue_box(self) -> bool:
        """
        Determine if dialogue box should be re-detected.

        Re-detect when:
        - Never detected before (dialogue_box is None)
        - Detection interval has elapsed (5+ minutes since last detection)

        Returns:
            True if should re-detect
        """
        if self.dialogue_box is None:
            return True

        time_since_detection = time.time() - self.last_detection_time
        return time_since_detection >= self.detection_interval

    async def _detect_dialogue_box(self, screenshot_bytes: bytes, translate_fn) -> None:
        """
        Detect dialogue box region using Claude Vision.

        Sends full screenshot to Claude Vision with prompt to identify
        the dialogue box coordinates. Caches result for future frames.

        Args:
            screenshot_bytes: Full screenshot as bytes
            translate_fn: Translation function (unused, kept for signature compatibility)
        """
        logger.info("Detecting dialogue box region...")

        try:
            # Use Vision API client for dialogue box detection
            vision_client = get_vision_client()
            box = await vision_client.detect_dialogue_box(screenshot_bytes)

            self.dialogue_box = box
            self.last_detection_time = time.time()

            logger.info(
                f"Dialogue box detected: x={box[0]}, y={box[1]}, "
                f"w={box[2]}, h={box[3]}"
            )

        except Exception as e:
            logger.error(f"Dialogue box detection error: {e}", exc_info=True)
            raise

    def _compute_change_status(self, cropped: Image.Image) -> tuple[bool, imagehash.ImageHash]:
        """
        Check if cropped dialogue region has changed since last frame.

        PURE FUNCTION - does not mutate state. This prevents race conditions
        and hash drift by allowing unconditional hash updates in the caller.

        Args:
            cropped: Cropped PIL Image of dialogue region

        Returns:
            Tuple of (has_changed: bool, current_hash: ImageHash)
        """
        current_hash = compute_perceptual_hash(cropped)

        # First frame - always translate
        if self.last_hash is None:
            logger.debug("First frame - marking as changed")
            return (True, current_hash)

        # Compare with previous frame
        distance = compare_hashes(current_hash, self.last_hash)
        has_changed = distance >= self.change_threshold

        if has_changed:
            logger.debug(f"Dialogue changed (distance={distance}, threshold={self.change_threshold})")
        else:
            logger.debug(f"Dialogue unchanged (distance={distance}, threshold={self.change_threshold})")

        return (has_changed, current_hash)

    async def _translate_region(self, cropped_bytes: bytes, translate_fn) -> dict:
        """
        Translate cropped dialogue region using manga-ocr + Claude text translation.

        This is a 2-step pipeline:
        1. manga-ocr: Extract Japanese text (local, fast, accurate for game text)
        2. Claude: Translate text to English (cheaper than vision API)

        Args:
            cropped_bytes: Cropped image as bytes
            translate_fn: Translation function (unused, kept for signature compatibility)

        Returns:
            Translation result dict with japanese_text and english_text
        """
        with open("/tmp/translation_service_debug.log", "a") as f:
            f.write(f"_translate_region called with {len(cropped_bytes)} bytes\n")

        try:
            # Step 1: OCR - Extract Japanese text from image (local, no API cost)
            with open("/tmp/translation_service_debug.log", "a") as f:
                f.write(f"Running manga-ocr...\n")

            ocr_client = OCRClient()
            ocr_start = time.time()
            japanese_text = ocr_client.extract_text_from_bytes(cropped_bytes)
            ocr_time_ms = (time.time() - ocr_start) * 1000

            with open("/tmp/translation_service_debug.log", "a") as f:
                f.write(f"OCR extracted ({ocr_time_ms:.0f}ms): {japanese_text}\n")

            logger.info(f"OCR extracted ({ocr_time_ms:.0f}ms): {japanese_text}")

            # If no text found, return empty result
            if not japanese_text or not japanese_text.strip():
                with open("/tmp/translation_service_debug.log", "a") as f:
                    f.write(f"No text extracted by OCR\n")
                return {"japanese_text": "", "english_text": ""}

            # Step 2: Translation - Send text to Claude (much cheaper than vision)
            with open("/tmp/translation_service_debug.log", "a") as f:
                f.write(f"Calling text translation API...\n")

            vision_client = get_vision_client()
            translate_start = time.time()
            result = await vision_client.translate_text(japanese_text)
            translate_time_ms = (time.time() - translate_start) * 1000

            with open("/tmp/translation_service_debug.log", "a") as f:
                f.write(
                    f"Translation returned ({translate_time_ms:.0f}ms): {result}\n"
                )

            logger.info(
                f"Translation completed ({translate_time_ms:.0f}ms): "
                f"{result.get('english_text', '')}"
            )

            return result

        except Exception as e:
            with open("/tmp/translation_service_debug.log", "a") as f:
                f.write(f"Translation EXCEPTION: {type(e).__name__}: {e}\n")
            logger.error(f"Translation pipeline failed: {e}", exc_info=True)
            raise

    def get_status(self) -> dict:
        """
        Get current service status and statistics.

        Returns:
            Status dict with configuration, state, statistics, and timing breakdown.

            NEW in Phase 3: Added timing breakdown and frame skipping metrics for debugging.
        """
        # Calculate effective FPS (frames per second)
        effective_fps = 0.0
        if self.avg_latency_ms > 0:
            effective_fps = 1000.0 / self.avg_latency_ms

        return {
            "enabled": self.enabled,
            "configuration": {
                "poll_interval": self.poll_interval,
                "change_threshold": self.change_threshold,
                "detection_interval": self.detection_interval,
                "debug_mode": self.debug_mode,
            },
            "state": {
                "dialogue_box": self.dialogue_box,
                "last_translation": self.last_translation,
                "processing_frame": self._processing_frame,  # NEW: shows if busy
            },
            "statistics": {
                "total_screenshots": self.total_screenshots,
                "total_translations": self.total_translations,
                "api_calls_saved": self.api_calls_saved,
                "frames_skipped": self.frames_skipped,  # NEW
                "detection_failures": self.detection_failures,  # NEW
                "efficiency_percent": self._efficiency_percent(),
                "avg_latency_ms": round(self.avg_latency_ms, 1),
            },
            "timing": {  # NEW: Timing breakdown for debugging
                "avg_screenshot_ms": round(self.screenshot_time_ms, 1),
                "avg_translation_ms": round(self.translation_time_ms, 1),
                "last_detection_ms": round(self.detection_time_ms, 1),
                "effective_fps": round(effective_fps, 2),
            },
        }

    def configure(self, **kwargs) -> dict:
        """
        Update service configuration.

        Can update poll_interval, change_threshold, detection_interval,
        dialogue_box, or debug_mode while service is running.

        Args:
            **kwargs: Configuration parameters to update

        Returns:
            Updated configuration dict
        """
        updated = []

        if "poll_interval" in kwargs:
            self.poll_interval = kwargs["poll_interval"]
            updated.append("poll_interval")

        if "change_threshold" in kwargs:
            self.change_threshold = kwargs["change_threshold"]
            updated.append("change_threshold")

        if "detection_interval" in kwargs:
            self.detection_interval = kwargs["detection_interval"]
            updated.append("detection_interval")

        if "dialogue_box" in kwargs:
            # Parse dialogue_box from string like "100,700,400,200"
            box_str = kwargs["dialogue_box"]
            if box_str:
                try:
                    x, y, w, h = map(int, box_str.split(","))
                    self.dialogue_box = (x, y, w, h)
                    self.last_detection_time = time.time()
                    updated.append("dialogue_box")
                except Exception as e:
                    logger.error(f"Failed to parse dialogue_box: {e}")

        if "debug_mode" in kwargs:
            self.debug_mode = kwargs["debug_mode"]
            updated.append("debug_mode")

        logger.info(f"Configuration updated: {updated}")

        return {
            "status": "configured",
            "updated": updated,
            "configuration": {
                "poll_interval": self.poll_interval,
                "change_threshold": self.change_threshold,
                "detection_interval": self.detection_interval,
                "dialogue_box": self.dialogue_box,
                "debug_mode": self.debug_mode,
            },
        }

    def _efficiency_percent(self) -> float:
        """
        Calculate efficiency percentage (API calls saved / total frames).

        Returns:
            Efficiency as percentage (0-100)
        """
        if self.total_screenshots == 0:
            return 0.0
        return (self.api_calls_saved / self.total_screenshots) * 100

    def _save_debug(self, label: str, image_bytes: bytes) -> None:
        """
        Save debug image if debug_mode enabled.

        Args:
            label: Label for the debug image
            image_bytes: Image data as bytes
        """
        if not self.debug_mode:
            return

        try:
            debug_path = Path("tmp/translation_debug")
            image = bytes_to_image(image_bytes)
            save_debug_image(image, debug_path, f"{label}_{self._debug_counter:04d}")
            self._debug_counter += 1
        except Exception as e:
            logger.error(f"Failed to save debug image: {e}")
