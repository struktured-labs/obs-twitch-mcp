"""
SSE (Server-Sent Events) server for broadcasting chat messages to browser overlays.

Runs on port 8765 by default. Browser sources connect to /events endpoint
to receive real-time chat messages.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from .logger import get_logger

logger = get_logger("sse_server")

# Global state
_server: "SSEServer | None" = None
_runner: web.AppRunner | None = None
_sse_loop: asyncio.AbstractEventLoop | None = None


@dataclass
class SSEServer:
    """Server-Sent Events server for chat overlay."""

    port: int = 8765
    host: str = "127.0.0.1"
    _clients: set = field(default_factory=set)
    _config: dict = field(default_factory=dict)
    _running: bool = False

    def __post_init__(self):
        self._config = {
            "theme": "retro",
            "fade_seconds": 60,
            "max_messages": 15,
            "show_avatars": True,
            "font_size": "medium",
            "direction": "up",
            "background": "transparent",
        }

    async def handle_events(self, request: web.Request) -> web.StreamResponse:
        """SSE endpoint - clients connect here to receive chat messages."""
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await response.prepare(request)

        # Register this client
        queue: asyncio.Queue = asyncio.Queue()
        self._clients.add(queue)
        logger.debug(f"SSE client connected ({len(self._clients)} total)")

        try:
            # Send initial config
            config_data = f"event: config\ndata: {json.dumps(self._config)}\n\n"
            await response.write(config_data.encode())

            # Send keepalive and messages
            while True:
                try:
                    # Wait for message with timeout for keepalive
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_data = f"data: {json.dumps(msg)}\n\n"
                    await response.write(event_data.encode())
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    await response.write(b": keepalive\n\n")
                except asyncio.CancelledError:
                    break

        except ConnectionResetError:
            pass
        finally:
            self._clients.discard(queue)
            logger.debug(f"SSE client disconnected ({len(self._clients)} remaining)")

        return response

    async def handle_config(self, request: web.Request) -> web.Response:
        """GET/POST config endpoint."""
        if request.method == "GET":
            return web.json_response(self._config)

        elif request.method == "POST":
            try:
                new_config = await request.json()
                self._config.update(new_config)
                # Broadcast config update to all clients
                await self._broadcast_config()
                return web.json_response({"status": "ok", "config": self._config})
            except Exception as e:
                return web.json_response({"status": "error", "message": str(e)}, status=400)

        return web.Response(status=405)

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "clients": len(self._clients),
            "config": self._config,
        })

    async def _broadcast_config(self) -> None:
        """Send config update to all connected clients."""
        config_data = {"type": "config", **self._config}
        for queue in self._clients:
            try:
                queue.put_nowait(config_data)
            except asyncio.QueueFull:
                pass

    async def broadcast_message(self, message: dict) -> None:
        """Broadcast a chat message to all connected clients."""
        if not self._clients:
            return

        for queue in self._clients:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Client is slow, skip this message
                pass

    def update_config(self, **kwargs) -> dict:
        """Update overlay configuration."""
        self._config.update(kwargs)
        # Schedule broadcast
        asyncio.create_task(self._broadcast_config())
        return self._config

    def get_config(self) -> dict:
        """Get current configuration."""
        return self._config.copy()

    @property
    def client_count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)


def get_sse_server() -> SSEServer | None:
    """Get the global SSE server instance."""
    return _server


async def broadcast_message(message: dict) -> None:
    """Broadcast a message to all connected overlay clients."""
    if _server:
        await _server.broadcast_message(message)


def broadcast_message_sync(message: dict) -> None:
    """Synchronous wrapper for broadcasting (for use from sync handlers).

    Uses run_coroutine_threadsafe to safely schedule the broadcast
    on the SSE server's event loop from any thread (e.g., chat listener thread).
    """
    if not _server:
        logger.warning("broadcast_message_sync: no SSE server")
        return
    if not _sse_loop:
        logger.warning("broadcast_message_sync: no SSE event loop stored")
        return
    if not _sse_loop.is_running():
        logger.warning("broadcast_message_sync: SSE event loop not running")
        return

    logger.debug(f"broadcast_message_sync: sending to {_server.client_count} clients: {message.get('username', '?')}")
    future = asyncio.run_coroutine_threadsafe(_server.broadcast_message(message), _sse_loop)
    # Check for exceptions (non-blocking)
    try:
        future.result(timeout=1.0)
    except Exception as e:
        logger.error(f"broadcast_message_sync failed: {e}")


async def start_sse_server(port: int = 8765, host: str = "127.0.0.1") -> SSEServer:
    """Start the SSE server."""
    global _server, _runner, _sse_loop

    if _server and _server._running:
        logger.info("SSE server already running")
        return _server

    # Override port from env if set
    port = int(os.getenv("SSE_SERVER_PORT", port))

    _server = SSEServer(port=port, host=host)

    app = web.Application()
    app.router.add_get("/events", _server.handle_events)
    app.router.add_get("/config", _server.handle_config)
    app.router.add_post("/config", _server.handle_config)
    app.router.add_get("/health", _server.handle_health)

    # Add CORS headers for all routes
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == "OPTIONS":
                return web.Response(headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                })
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response
        return middleware_handler

    app.middlewares.append(cors_middleware)

    _runner = web.AppRunner(app)
    await _runner.setup()

    site = web.TCPSite(_runner, host, port)
    await site.start()

    _server._running = True
    _sse_loop = asyncio.get_event_loop()
    logger.info(f"SSE server started on http://{host}:{port}")
    logger.info(f"  /events - SSE stream for chat overlay")
    logger.info(f"  /config - GET/POST overlay configuration")
    logger.info(f"  /health - Health check")

    return _server


async def stop_sse_server() -> None:
    """Stop the SSE server."""
    global _server, _runner

    if _runner:
        await _runner.cleanup()
        _runner = None

    if _server:
        _server._running = False
        _server = None
        logger.info("SSE server stopped")
