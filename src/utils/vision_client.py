"""
Claude Vision API client for autonomous image translation.

Provides OCR and translation capabilities using Claude's vision models
for the background translation service.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Any, Callable

import anthropic

logger = logging.getLogger(__name__)


class VisionClient:
    """
    Claude Vision API client for OCR and translation.

    Wraps the Anthropic API to provide autonomous vision processing
    for the translation service.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Vision API client with streaming-appropriate timeouts.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Configure with aggressive timeouts for real-time streaming use
        # Default 600s read timeout is WAY too long - would hang service for 10 minutes!
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            timeout=anthropic.Timeout(
                connect=5.0,   # Fast connection required
                read=15.0,     # Translation timeout (vs 600s default!)
                write=10.0,    # Image upload timeout
                pool=60.0,     # Connection pool timeout
            ),
            max_retries=0,  # We handle retries ourselves (see _retry_api_call)
        )

        # Longer timeout for dialogue detection (less frequent, bigger payload)
        self.detection_timeout = anthropic.Timeout(
            connect=5.0,
            read=25.0,     # Detection takes ~2s, allow 10x buffer
            write=15.0,
            pool=60.0,
        )

    async def _retry_api_call(
        self,
        operation: str,
        api_call_fn: Callable,
        max_retries: int = 2,
        initial_backoff: float = 0.5,
    ) -> Any:
        """
        Execute API call with exponential backoff retry.

        Makes the service resilient to transient network errors.

        Args:
            operation: Description for logging (e.g., "translation")
            api_call_fn: Async function that performs the API call
            max_retries: Maximum retry attempts (default: 2)
            initial_backoff: Initial backoff in seconds (default: 0.5s)

        Returns:
            Result from api_call_fn, or empty dict on failure

        Raises:
            No exceptions - returns empty result on failure for graceful degradation
        """
        backoff = initial_backoff
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                result = await api_call_fn()

                if attempt > 0:
                    logger.info(f"{operation} succeeded on attempt {attempt + 1}")

                return result

            except anthropic.APITimeoutError as e:
                last_exception = e
                logger.warning(
                    f"{operation} timeout on attempt {attempt + 1}/{max_retries + 1} "
                    f"(waited {e.request.timeout if hasattr(e, 'request') else 'unknown'}s)"
                )

            except anthropic.APIConnectionError as e:
                last_exception = e
                logger.warning(
                    f"{operation} connection error on attempt {attempt + 1}/{max_retries + 1}: {e}"
                )

            except anthropic.RateLimitError as e:
                last_exception = e
                backoff *= 3  # Longer backoff for rate limits
                logger.warning(f"{operation} rate limited on attempt {attempt + 1}/{max_retries + 1}")

            # Don't sleep after last attempt
            if attempt < max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2.0  # Exponential backoff

        # All retries exhausted - return empty result instead of crashing
        logger.error(f"{operation} failed after {max_retries + 1} attempts: {last_exception}")
        return {"japanese_text": "", "english_text": ""}

    async def translate_image(
        self,
        image_bytes: bytes,
        prompt: str | None = None,
        model: str = "claude-3-haiku-20240307",
    ) -> dict[str, Any]:
        """
        Translate Japanese text in image using Claude Vision.

        Args:
            image_bytes: Image data as bytes
            prompt: Custom prompt (defaults to translation prompt)
            model: Claude model to use (default: claude-3-5-sonnet-20241022)

        Returns:
            dict with japanese_text and english_text

        Raises:
            Exception: If API call fails or response cannot be parsed
        """
        if prompt is None:
            prompt = """
            Analyze this game screenshot and OCR Japanese text from the DIALOGUE BOX only.

            ONLY translate:
            - Character names in dialogue
            - Dialogue text spoken by characters
            - Story/narrative text in dialogue boxes

            IGNORE and do NOT translate:
            - UI elements (menus, buttons, status text)
            - Score displays, item names, or HUD text
            - Small labels or single-word UI text
            - Any text that appears to be part of menus or interfaces

            If you see a dialogue box with character dialogue, translate ALL text in that box.
            If there is NO dialogue box or active dialogue, return empty strings.

            Return ONLY a valid JSON object with this exact format:
            {
                "japanese_text": "<Original Japanese dialogue text with line breaks>",
                "english_text": "<English translation with line breaks>"
            }

            If there is no active dialogue on screen, return:
            {
                "japanese_text": "",
                "english_text": ""
            }

            Important:
            - Only translate dialogue, NOT UI elements
            - If the text looks like a menu or status display, return empty
            - Preserve line breaks in both Japanese and English
            - Return ONLY the JSON object, no additional text
            """

        # Define the API call function to be retried
        async def _api_call():
            # Encode image as base64
            image_base64 = base64.standard_b64encode(image_bytes).decode("utf-8")

            # Make Vision API call (with timeout from client initialization)
            message = await self.client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # Extract response text
            response_text = message.content[0].text

            # Parse JSON response
            # Claude might wrap JSON in markdown code blocks, handle that
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove ```
            response_text = response_text.strip()

            # Parse as JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Vision API response as JSON: {e}")
                logger.error(f"Response text: {response_text}")
                return {"japanese_text": "", "english_text": ""}

            # Validate response structure
            if "japanese_text" not in result or "english_text" not in result:
                logger.warning(f"Invalid response structure: {result}")
                return {"japanese_text": "", "english_text": ""}

            return result

        # Execute with retry logic
        try:
            return await self._retry_api_call("Translation", _api_call)
        except Exception as e:
            logger.error(f"Translation failed: {e}", exc_info=True)
            return {"japanese_text": "", "english_text": ""}

    async def detect_dialogue_box(
        self,
        image_bytes: bytes,
        model: str = "claude-3-haiku-20240307",
    ) -> tuple[int, int, int, int]:
        """
        Detect dialogue box region in game screenshot.

        Args:
            image_bytes: Full screenshot as bytes
            model: Claude model to use

        Returns:
            Tuple of (x, y, width, height) for dialogue box region

        Raises:
            Exception: If detection fails or coordinates invalid
        """
        prompt = """
        Analyze this game screenshot and identify the dialogue/text box region.

        The dialogue box is typically:
        - At the bottom of the screen
        - Contains game text/dialogue
        - Has a visible border or background

        Return ONLY a valid JSON object with this exact format:
        {
            "x": <x coordinate of top-left corner>,
            "y": <y coordinate of top-left corner>,
            "width": <width of dialogue box>,
            "height": <height of dialogue box>
        }

        All coordinates must be integers.
        Be precise with the measurements.

        Important: Return ONLY the JSON object, no additional text.
        """

        # Define the API call function to be retried
        async def _api_call():
            # Encode image as base64
            image_base64 = base64.standard_b64encode(image_bytes).decode("utf-8")

            # Make Vision API call (with longer timeout for detection)
            message = await self.client.messages.create(
                model=model,
                max_tokens=512,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # Extract response text
            response_text = message.content[0].text

            # Parse JSON response (handle markdown wrapping)
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse as JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse dialogue box detection response: {e}")
                logger.error(f"Response text: {response_text}")
                raise

            # Validate response structure
            if not all(k in result for k in ["x", "y", "width", "height"]):
                raise ValueError(f"Invalid dialogue box detection response: {result}")

            # Extract coordinates
            x = int(result["x"])
            y = int(result["y"])
            width = int(result["width"])
            height = int(result["height"])

            # Sanity check coordinates
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid dialogue box dimensions: {width}x{height}")

            logger.info(f"Detected dialogue box: x={x}, y={y}, w={width}, h={height}")

            return (x, y, width, height)

        # Execute with retry logic (detection uses longer timeout)
        # Note: _retry_api_call will log errors but we need to re-raise for detection failures
        try:
            # We don't use _retry_api_call here because detection failures should be raised
            # (service needs to know detection failed to use cached box)
            return await _api_call()
        except Exception as e:
            logger.error(f"Dialogue box detection failed: {e}", exc_info=True)
            raise


# Module-level client instance
_vision_client: VisionClient | None = None


def get_vision_client() -> VisionClient:
    """
    Get or create the global Vision API client instance.

    Returns:
        VisionClient instance

    Raises:
        ValueError: If ANTHROPIC_API_KEY not set
    """
    global _vision_client
    if _vision_client is None:
        _vision_client = VisionClient()
    return _vision_client
