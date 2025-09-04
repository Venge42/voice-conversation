#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import json
import time
from typing import Optional

from loguru import logger
from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.observers.base_observer import BaseObserver

from crystal_light_controller import CrystalLightController
from state import *


class SpeakingLightObserver(BaseObserver):
    """
    Observer that detects speaking events and controls crystal lights.
    Monitors TTS frames to determine when the bot starts and stops speaking.
    Sends light commands to the client via WebSocket.
    """

    def __init__(self, light_controller: CrystalLightController, websocket_client=None):
        super().__init__()
        self.light_controller = light_controller
        self.websocket_client = websocket_client
        self.logger = logger.bind(
            connection=light_controller.connection_id, bot=light_controller.bot_config
        )

        # State tracking
        self.is_currently_speaking = False
        self.last_audio_frame_time = 0.0
        self.speaking_timeout = 0.5  # Stop speaking if no audio for 500ms
        self.timeout_task: Optional[asyncio.Task] = None

    async def on_frame(self, frame):
        """Handle incoming frames and detect speaking events"""
        try:
            # Log all frames for debugging
            frame_type = type(frame).__name__
            self.logger.info(f"🎯 Frame received: {frame_type}")
            self.logger.info(f"🎯 Frame type: {type(frame)}")
            self.logger.info(
                f"🎯 Frame dir: {[attr for attr in dir(frame) if not attr.startswith('_')]}"
            )

            # Handle TTS start frame
            if isinstance(frame, TTSStartedFrame):
                self.logger.info(
                    "🎤 TTSStartedFrame detected - starting speaking light effect"
                )
                await self._handle_speaking_start()

            # Handle TTS stop frame
            elif isinstance(frame, TTSStoppedFrame):
                self.logger.info(
                    "🔇 TTSStoppedFrame detected - stopping speaking light effect"
                )
                await self._handle_speaking_stop()

            # Handle audio frames to track active speaking
            elif isinstance(frame, TTSAudioRawFrame):
                self.logger.debug(
                    "🔊 TTSAudioRawFrame received - maintaining speaking state"
                )
                await self._handle_audio_frame()

            else:
                self.logger.debug(f"📡 Other frame type: {frame_type}")

        except Exception as e:
            self.logger.error(f"Error in SpeakingLightObserver: {e}")

    async def _handle_speaking_start(self):
        """Handle when TTS starts speaking"""
        if not self.is_currently_speaking:
            self.is_currently_speaking = True
            self.logger.info("TTS started - beginning speaking light effect")

            # Send start command to client
            await self._send_speaking_command("speaking_start")

            # Cancel any existing timeout
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()

    async def _handle_speaking_stop(self):
        """Handle when TTS stops speaking"""
        if self.is_currently_speaking:
            self.is_currently_speaking = False
            self.logger.info("TTS stopped - ending speaking light effect")

            # Send stop command to client
            await self._send_speaking_command("speaking_stop")

            # Cancel timeout task
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()

    async def _handle_audio_frame(self):
        """Handle audio frames to track active speaking"""
        current_time = time.time()
        self.last_audio_frame_time = current_time

        # If we're not currently marked as speaking but receiving audio,
        # we might have missed the TTSStartedFrame, so start speaking
        if not self.is_currently_speaking:
            await self._handle_speaking_start()

        # Reset timeout task
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()

        # Set up new timeout task
        self.timeout_task = asyncio.create_task(self._check_speaking_timeout())

    async def _check_speaking_timeout(self):
        """Check if speaking has timed out due to no audio frames"""
        try:
            await asyncio.sleep(self.speaking_timeout)

            # If no audio frames received during timeout, stop speaking
            current_time = time.time()
            if (
                self.is_currently_speaking
                and current_time - self.last_audio_frame_time >= self.speaking_timeout
            ):
                self.logger.info("Speaking timeout - no audio frames received")
                self._handle_speaking_stop()

        except asyncio.CancelledError:
            # Timeout was cancelled, which is normal
            pass
        except Exception as e:
            self.logger.error(f"Error in speaking timeout check: {e}")

    def on_error(self, error):
        """Handle errors in the observer"""
        self.logger.error(f"SpeakingLightObserver error: {error}")

        # On error, stop speaking to be safe
        if self.is_currently_speaking:
            self._handle_speaking_stop()

    async def cleanup(self):
        """Clean up the observer"""
        self.logger.info("Cleaning up SpeakingLightObserver")

        # Cancel timeout task
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass

        # Stop speaking if active
        if self.is_currently_speaking:
            self._handle_speaking_stop()

    async def _send_speaking_command(self, command_type: str):
        """Send simple speaking start/stop command to client"""
        try:
            import server

            speaking_command = {
                "type": command_type,
                "bot_config": self.light_controller.bot_config,
                "timestamp": time.time(),
            }

            # Send to light WebSocket if available
            connection_id = self.light_controller.connection_id
            if connection_id in server.light_websocket_connections:
                light_ws = server.light_websocket_connections[connection_id]
                await light_ws.send_text(json.dumps(speaking_command))
                self.logger.info(f"✅ Speaking command sent: {command_type}")
            else:
                self.logger.warning(
                    f"❌ No light WebSocket connection found for {connection_id}"
                )

        except Exception as e:
            self.logger.error(f"❌ Error sending speaking command: {e}")

    def get_status(self) -> dict:
        """Get current status of the observer"""
        return {
            "is_currently_speaking": self.is_currently_speaking,
            "last_audio_frame_time": self.last_audio_frame_time,
            "speaking_timeout": self.speaking_timeout,
        }
