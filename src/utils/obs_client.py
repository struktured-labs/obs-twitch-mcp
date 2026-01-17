"""
OBS WebSocket client wrapper.
"""

import base64
from dataclasses import dataclass

import obsws_python as obs


@dataclass
class OBSClient:
    """Wrapper for OBS WebSocket client."""

    host: str
    port: int
    password: str
    _client: obs.ReqClient | None = None

    @property
    def client(self) -> obs.ReqClient:
        """Get or create the OBS client connection."""
        if self._client is None:
            self._client = obs.ReqClient(
                host=self.host,
                port=self.port,
                password=self.password,
            )
        return self._client

    def get_version(self) -> dict:
        """Get OBS version info."""
        v = self.client.get_version()
        return {
            "obs_version": v.obs_version,
            "websocket_version": v.obs_web_socket_version,
            "platform": v.platform,
        }

    def get_stats(self) -> dict:
        """Get OBS statistics."""
        s = self.client.get_stats()
        return {
            "cpu_usage": s.cpu_usage,
            "memory_usage": s.memory_usage,
            "active_fps": s.active_fps,
            "render_skipped_frames": s.render_skipped_frames,
            "output_skipped_frames": s.output_skipped_frames,
        }

    def list_scenes(self) -> list[str]:
        """List all scene names."""
        scenes = self.client.get_scene_list()
        return [s["sceneName"] for s in scenes.scenes]

    def get_current_scene(self) -> str:
        """Get current program scene name."""
        return self.client.get_current_program_scene().scene_name

    def switch_scene(self, scene_name: str) -> None:
        """Switch to a scene."""
        self.client.set_current_program_scene(scene_name)

    def get_scene_items(self, scene_name: str) -> list[dict]:
        """Get items in a scene."""
        items = self.client.get_scene_item_list(scene_name)
        return [
            {
                "id": item["sceneItemId"],
                "name": item["sourceName"],
                "enabled": item["sceneItemEnabled"],
            }
            for item in items.scene_items
        ]

    def get_scene_item_transform(self, scene_name: str, item_id: int) -> dict:
        """Get the transform (position, size, etc.) of a scene item."""
        result = self.client.get_scene_item_transform(scene_name, item_id)
        return result.scene_item_transform

    def set_scene_item_enabled(self, scene_name: str, item_id: int, enabled: bool) -> None:
        """Enable or disable a scene item (show/hide)."""
        self.client.set_scene_item_enabled(scene_name, item_id, enabled)

    def create_text_source(
        self,
        scene_name: str,
        source_name: str,
        text: str,
        font_size: int = 60,
        color: int = 0xFFFFFFFF,
    ) -> int:
        """Create a text source in a scene."""
        self.client.create_input(
            scene_name,
            source_name,
            "text_ft2_source_v2",
            {
                "text": text,
                "font": {"face": "Sans Serif", "size": font_size},
                "color1": color,
                "color2": color,
            },
            True,
        )
        item_id = self.client.get_scene_item_id(scene_name, source_name).scene_item_id
        return item_id

    def set_source_text(self, source_name: str, text: str) -> None:
        """Update text on a text source."""
        self.client.set_input_settings(source_name, {"text": text}, True)

    def set_input_settings(self, source_name: str, settings: dict, overlay: bool = True) -> None:
        """Update settings on any input/source.

        Args:
            source_name: Name of the source to update
            settings: Dict of settings to update
            overlay: If True, merge with existing settings. If False, replace all.
        """
        self.client.set_input_settings(source_name, settings, overlay)

    def get_input_settings(self, source_name: str) -> dict:
        """Get current settings for an input/source."""
        result = self.client.get_input_settings(source_name)
        return {
            "settings": result.input_settings,
            "kind": result.input_kind,
        }

    def remove_source(self, source_name: str) -> None:
        """Remove a source completely from OBS (from all scenes and the input list)."""
        # First, remove the scene item from ALL scenes that reference it
        scenes = self.list_scenes()
        for scene in scenes:
            try:
                item_id = self.client.get_scene_item_id(scene, source_name).scene_item_id
                self.client.remove_scene_item(scene, item_id)
            except Exception:
                pass  # Source not in this scene

        # Now remove the input itself
        try:
            self.client.remove_input(source_name)
        except Exception:
            pass  # Input may already be gone if it was only in one scene

    def list_inputs(self) -> list[dict]:
        """List all inputs (sources) in OBS."""
        result = self.client.get_input_list()
        return [
            {
                "name": inp["inputName"],
                "kind": inp["inputKind"],
            }
            for inp in result.inputs
        ]

    def set_scene_item_transform(
        self,
        scene_name: str,
        item_id: int,
        x: float | None = None,
        y: float | None = None,
        alignment: int = 0,
    ) -> None:
        """Set position of a scene item."""
        transform = {"alignment": alignment}
        if x is not None:
            transform["positionX"] = x
        if y is not None:
            transform["positionY"] = y
        self.client.set_scene_item_transform(scene_name, item_id, transform)

    def set_volume(self, source_name: str, volume_db: float) -> None:
        """Set volume of an audio source in dB."""
        self.client.set_input_volume(source_name, None, volume_db)

    def set_mute(self, source_name: str, muted: bool) -> None:
        """Mute or unmute an audio source."""
        self.client.set_input_mute(source_name, muted)

    def get_screenshot(self, source_name: str | None = None, width: int = 1920, height: int = 1080) -> bytes:
        """Capture screenshot of a source or current scene."""
        if source_name is None:
            source_name = self.get_current_scene()

        result = self.client.get_source_screenshot(
            name=source_name,
            img_format="png",
            width=width,
            height=height,
            quality=85,
        )
        # Remove data URL prefix if present
        data = result.image_data
        if "," in data:
            data = data.split(",")[1]
        return base64.b64decode(data)

    def create_browser_source(
        self,
        scene_name: str,
        source_name: str,
        url: str,
        width: int = 1920,
        height: int = 1080,
    ) -> int:
        """Create a browser source."""
        self.client.create_input(
            scene_name,
            source_name,
            "browser_source",
            {
                "url": url,
                "width": width,
                "height": height,
                "reroute_audio": True,
            },
            True,
        )
        item_id = self.client.get_scene_item_id(scene_name, source_name).scene_item_id
        return item_id

    def create_media_source(
        self,
        scene_name: str,
        source_name: str,
        file_path: str,
        loop: bool = False,
    ) -> int:
        """Create a media source for video/audio files."""
        self.client.create_input(
            scene_name,
            source_name,
            "ffmpeg_source",
            {
                "local_file": file_path,
                "is_local_file": True,
                "looping": loop,
            },
            True,
        )
        item_id = self.client.get_scene_item_id(scene_name, source_name).scene_item_id
        return item_id

    # Replay Buffer methods
    def get_replay_buffer_status(self) -> dict:
        """Get replay buffer status."""
        try:
            result = self.client.get_replay_buffer_status()
            return {
                "active": result.output_active,
            }
        except Exception as e:
            return {"active": False, "error": str(e)}

    def start_replay_buffer(self) -> None:
        """Start the replay buffer."""
        self.client.start_replay_buffer()

    def stop_replay_buffer(self) -> None:
        """Stop the replay buffer."""
        self.client.stop_replay_buffer()

    def save_replay_buffer(self) -> str:
        """Save the current replay buffer. Returns the saved file path."""
        result = self.client.save_replay_buffer()
        # Wait a moment for the file to be saved
        import time
        time.sleep(0.5)
        # Get the last replay path
        try:
            output = self.client.get_last_replay_buffer_replay()
            return output.saved_replay_path
        except Exception:
            return "Replay saved (path unavailable)"

    # Recording methods
    def get_record_status(self) -> dict:
        """Get recording status."""
        try:
            result = self.client.get_record_status()
            return {
                "active": result.output_active,
                "paused": result.output_paused,
                "timecode": result.output_timecode,
                "duration": result.output_duration,
                "bytes": result.output_bytes,
            }
        except Exception as e:
            return {"active": False, "error": str(e)}

    def start_record(self) -> None:
        """Start recording."""
        self.client.start_record()

    def stop_record(self) -> str:
        """Stop recording and return the output file path."""
        result = self.client.stop_record()
        return result.output_path

    def pause_record(self) -> None:
        """Pause recording."""
        self.client.pause_record()

    def resume_record(self) -> None:
        """Resume recording."""
        self.client.resume_record()

    def add_source_to_scene(self, scene_name: str, source_name: str, enabled: bool = True) -> int:
        """Add an existing source/input to a scene.

        Args:
            scene_name: Scene to add the source to
            source_name: Name of the existing source/input
            enabled: Whether the source should be visible (default: True)

        Returns:
            The scene item ID of the newly created item
        """
        result = self.client.create_scene_item(scene_name, source_name, enabled)
        return result.scene_item_id

    # Filter methods
    def get_source_filter_list(self, source_name: str) -> list[dict]:
        """Get list of all filters on a source.

        Args:
            source_name: Name of the source

        Returns:
            List of filter dicts with name, kind, index, enabled status
        """
        result = self.client.get_source_filter_list(source_name)
        return [
            {
                "name": f.filter_name,
                "kind": f.filter_kind,
                "index": f.filter_index,
                "enabled": f.filter_enabled,
            }
            for f in result.filters
        ]

    def get_source_filter(self, source_name: str, filter_name: str) -> dict:
        """Get settings for a specific filter.

        Args:
            source_name: Name of the source
            filter_name: Name of the filter

        Returns:
            Dict with filter settings
        """
        result = self.client.get_source_filter(source_name, filter_name)
        return {
            "name": filter_name,
            "kind": result.filter_kind,
            "index": result.filter_index,
            "enabled": result.filter_enabled,
            "settings": result.filter_settings,
        }

    def set_source_filter_settings(
        self, source_name: str, filter_name: str, settings: dict, overlay: bool = True
    ) -> None:
        """Update filter settings in real-time.

        Args:
            source_name: Name of the source
            filter_name: Name of the filter
            settings: Dict of settings to update
            overlay: If True, merge with existing settings. If False, replace all settings.
        """
        self.client.set_source_filter_settings(source_name, filter_name, settings, overlay)

    def set_source_filter_enabled(self, source_name: str, filter_name: str, enabled: bool) -> None:
        """Enable or disable a filter.

        Args:
            source_name: Name of the source
            filter_name: Name of the filter
            enabled: True to enable, False to disable
        """
        self.client.set_source_filter_enabled(source_name, filter_name, enabled)
