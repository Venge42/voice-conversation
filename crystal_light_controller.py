#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import aiohttp
from loguru import logger


@dataclass
class Color:
    """Represents an RGBA color with values between 0.0 and 1.0"""

    r: float
    g: float
    b: float
    a: float = 1.0

    def to_shelly_format(self) -> Tuple[int, int, int, int]:
        """Convert to Shelly RGBW format (0-255) with alpha applied to RGB"""
        alpha = int(self.a * 255)
        red = int(self.r * 255 * self.a)
        green = int(self.g * 255 * self.a)
        blue = int(self.b * 255 * self.a)
        white = 0  # We don't use white channel
        return red, green, blue, white

    def clamp(self) -> "Color":
        """Clamp all color values to valid range [0.0, 1.0]"""
        return Color(
            max(0.0, min(1.0, self.r)),
            max(0.0, min(1.0, self.g)),
            max(0.0, min(1.0, self.b)),
            max(0.0, min(1.0, self.a)),
        )

    def __add__(self, other: "Color") -> "Color":
        return Color(
            self.r + other.r, self.g + other.g, self.b + other.b, self.a + other.a
        )

    def __mul__(self, scalar: float) -> "Color":
        return Color(self.r * scalar, self.g * scalar, self.b * scalar, self.a * scalar)

    def lerp(self, other: "Color", t: float) -> "Color":
        """Linear interpolation between this color and another color.
        t=0 returns this color, t=1 returns other color.
        """
        return Color(
            self.r + (other.r - self.r) * t,
            self.g + (other.g - self.g) * t,
            self.b + (other.b - self.b) * t,
            self.a + (other.a - self.a) * t,
        )


@dataclass
class LightConfig:
    """Configuration for crystal light effects"""

    primary_color: Color
    fade_to_color: Color  # Color to fade towards for variation
    off_color: Color
    variation_intensity: float  # How much color variation (0.0-1.0)
    color_shift_speed: float  # Speed of color shifting
    pulse_intensity: float  # Intensity of pulsing effect
    pulse_speed: float  # Speed of pulsing
    breathing_effect: bool  # Enable breathing effect
    breathing_speed: float  # Speed of breathing
    breathing_intensity: float  # Intensity of breathing
    shelly_ip: str  # IP address of Shelly device


class CrystalLightController:
    """
    Sophisticated light controller for crystal speaking effects.
    Inspired by Unity's SpeakingCrystal and LightController scripts.
    """

    def __init__(self, bot_config: str, connection_id: str):
        self.bot_config = bot_config
        self.connection_id = connection_id
        self.logger = logger.bind(connection=connection_id, bot=bot_config)

        # Load configuration
        self.config = self._load_light_config()

        # State management
        self.is_speaking = False
        self.speaking_start_time = 0.0
        self.current_color = self.config.off_color
        self.target_color = self.config.primary_color

        # Animation state
        self.color_shift_phase = random.uniform(0, 2 * math.pi)
        self.pulse_phase = random.uniform(0, 2 * math.pi)
        self.breathing_phase = random.uniform(0, 2 * math.pi)

        # Task management
        self.light_task: Optional[asyncio.Task] = None
        self.session: Optional[aiohttp.ClientSession] = None

    def _load_light_config(self) -> LightConfig:
        """Load light configuration from bot config file"""
        config_file = Path(f"lore/bots/{self.bot_config}/config.json")

        if not config_file.exists():
            self.logger.warning(
                f"Config file {config_file} not found, using default light config"
            )
            return self._get_default_config()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                light_config_data = config_data.get("light_config", {})

                if not light_config_data:
                    self.logger.warning(
                        f"No light_config found in {config_file}, using default"
                    )
                    return self._get_default_config()

                # Parse colors
                primary_color_data = light_config_data.get("primary_color", {})
                fade_to_color_data = light_config_data.get("fade_to_color", {})
                off_color_data = light_config_data.get("off_color", {})

                primary_color = Color(
                    primary_color_data.get("r", 0.8),
                    primary_color_data.get("g", 0.2),
                    primary_color_data.get("b", 1.0),
                    primary_color_data.get("a", 1.0),
                )

                # If no fade_to_color specified, create a complementary color
                if not fade_to_color_data:
                    # Create a complementary color by shifting hue
                    fade_to_color = Color(
                        primary_color_data.get("g", 0.2),  # Use G as R
                        primary_color_data.get("b", 1.0),  # Use B as G
                        primary_color_data.get("r", 0.8),  # Use R as B
                        primary_color_data.get("a", 1.0),
                    )
                else:
                    fade_to_color = Color(
                        fade_to_color_data.get("r", 0.2),
                        fade_to_color_data.get("g", 1.0),
                        fade_to_color_data.get("b", 0.8),
                        fade_to_color_data.get("a", 1.0),
                    )

                off_color = Color(
                    off_color_data.get("r", 0.0),
                    off_color_data.get("g", 0.0),
                    off_color_data.get("b", 0.0),
                    off_color_data.get("a", 0.0),
                )

                return LightConfig(
                    primary_color=primary_color,
                    fade_to_color=fade_to_color,
                    off_color=off_color,
                    variation_intensity=light_config_data.get(
                        "variation_intensity", 0.3
                    ),
                    color_shift_speed=light_config_data.get("color_shift_speed", 2.0),
                    pulse_intensity=light_config_data.get("pulse_intensity", 0.2),
                    pulse_speed=light_config_data.get("pulse_speed", 1.5),
                    breathing_effect=light_config_data.get("breathing_effect", True),
                    breathing_speed=light_config_data.get("breathing_speed", 0.8),
                    breathing_intensity=light_config_data.get(
                        "breathing_intensity", 0.15
                    ),
                    shelly_ip=light_config_data.get("shelly_ip", "192.168.2.77"),
                )

        except Exception as e:
            self.logger.error(f"Error loading light config: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> LightConfig:
        """Get default light configuration"""
        return LightConfig(
            primary_color=Color(0.8, 0.2, 1.0, 1.0),  # Purple
            fade_to_color=Color(0.2, 1.0, 0.8, 1.0),  # Complementary cyan
            off_color=Color(0.0, 0.0, 0.0, 0.0),  # Black/off
            variation_intensity=0.3,
            color_shift_speed=2.0,
            pulse_intensity=0.2,
            pulse_speed=1.5,
            breathing_effect=True,
            breathing_speed=0.8,
            breathing_intensity=0.15,
            shelly_ip="192.168.2.77",
        )

    async def start_speaking(self):
        """Start the speaking light effect"""
        if self.is_speaking:
            return

        self.is_speaking = True
        self.speaking_start_time = time.time()

        self.logger.info("Starting speaking light effect")

        # Initialize HTTP session if not exists
        if not self.session:
            self.session = aiohttp.ClientSession()

        # Start the light animation task
        if self.light_task and not self.light_task.done():
            self.light_task.cancel()

        self.light_task = asyncio.create_task(self._light_animation_loop())

    async def stop_speaking(self):
        """Stop the speaking light effect and return to off state"""
        if not self.is_speaking:
            return

        self.is_speaking = False

        self.logger.info("Stopping speaking light effect")

        # Cancel animation task
        if self.light_task and not self.light_task.done():
            self.light_task.cancel()

        # Set to off color
        await self._set_light_color(self.config.off_color)

    async def _light_animation_loop(self):
        """Main animation loop for speaking effects"""
        try:
            while self.is_speaking:
                current_time = time.time()
                elapsed_time = current_time - self.speaking_start_time

                # Calculate animated color
                animated_color = self._calculate_animated_color(elapsed_time)

                # Apply the color
                await self._set_light_color(animated_color)

                # Update phases for next frame
                self._update_animation_phases()

                # Sleep for smooth animation (target ~30 FPS)
                await asyncio.sleep(1.0 / 30.0)

        except asyncio.CancelledError:
            self.logger.debug("Light animation loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in light animation loop: {e}")

    def _calculate_animated_color(self, elapsed_time: float) -> Color:
        """Calculate the current animated color based on time and effects"""
        # Color shifting effect - interpolate between primary and fade_to color
        color_shift_factor = self._calculate_color_shift_factor(elapsed_time)
        base_color = self.config.primary_color.lerp(
            self.config.fade_to_color, color_shift_factor
        )

        # Pulsing effect - brightness variation
        pulse_factor = self._calculate_pulse_factor(elapsed_time)

        # Breathing effect - alpha/intensity variation
        breathing_factor = self._calculate_breathing_factor(elapsed_time)

        # Apply brightness and breathing effects
        final_color = base_color * pulse_factor * breathing_factor

        return final_color.clamp()

    def _calculate_color_shift_factor(self, elapsed_time: float) -> float:
        """Calculate color shift factor for interpolation between primary and fade_to color"""
        if self.config.variation_intensity <= 0:
            return 0.0

        # Use multiple sine waves for complex color shifting
        phase1 = self.color_shift_phase + elapsed_time * self.config.color_shift_speed
        phase2 = (
            self.color_shift_phase + elapsed_time * self.config.color_shift_speed * 1.3
        )
        phase3 = (
            self.color_shift_phase + elapsed_time * self.config.color_shift_speed * 0.7
        )

        # Combine multiple sine waves for organic variation
        shift1 = math.sin(phase1) * 0.4
        shift2 = math.sin(phase2) * 0.3
        shift3 = math.sin(phase3) * 0.3

        # Combine shifts and scale by variation intensity
        combined_shift = (shift1 + shift2 + shift3) / 3.0
        shift_factor = (combined_shift + 1.0) / 2.0  # Normalize to 0-1 range

        # Apply variation intensity
        return shift_factor * self.config.variation_intensity

    def _calculate_pulse_factor(self, elapsed_time: float) -> float:
        """Calculate pulsing brightness factor"""
        if self.config.pulse_intensity <= 0:
            return 1.0

        pulse_phase = self.pulse_phase + elapsed_time * self.config.pulse_speed
        pulse = math.sin(pulse_phase) * self.config.pulse_intensity

        # Ensure minimum brightness
        return max(0.3, 1.0 + pulse)

    def _calculate_breathing_factor(self, elapsed_time: float) -> float:
        """Calculate breathing effect factor"""
        if not self.config.breathing_effect or self.config.breathing_intensity <= 0:
            return 1.0

        breathing_phase = (
            self.breathing_phase + elapsed_time * self.config.breathing_speed
        )
        breathing = math.sin(breathing_phase) * self.config.breathing_intensity

        # Breathing affects alpha/intensity
        return max(0.5, 1.0 + breathing)

    def _update_animation_phases(self):
        """Update animation phases for next frame"""
        # Add small random variations to prevent predictable patterns
        self.color_shift_phase += random.uniform(-0.1, 0.1)
        self.pulse_phase += random.uniform(-0.05, 0.05)
        self.breathing_phase += random.uniform(-0.08, 0.08)

    async def _set_light_color(self, color: Color):
        """Send color command to client via WebSocket (client will control Shelly device)"""
        # Only send if color changed significantly (avoid spam)
        if not hasattr(self, "_last_sent_color") or self._color_changed_significantly(
            color
        ):
            # Store the current color for status reporting
            self.current_color = color
            self._last_sent_color = color

            # Send light command to client via WebSocket
            try:
                import server

                light_command = self.get_light_command()

                # Send to light WebSocket if available
                if self.connection_id in server.light_websocket_connections:
                    light_ws = server.light_websocket_connections[self.connection_id]
                    await light_ws.send_text(json.dumps(light_command))
                    self.logger.debug(f"🎨 Light command sent: {light_command}")
                else:
                    self.logger.warning(
                        f"❌ No light WebSocket connection found for {self.connection_id}"
                    )

            except Exception as e:
                self.logger.error(f"❌ Error sending light command: {e}")
        else:
            # Just update internal state without sending
            self.current_color = color

    def _color_changed_significantly(self, new_color: Color) -> bool:
        """Check if color changed enough to warrant sending a new command"""
        if not hasattr(self, "_last_sent_color"):
            return True

        # Calculate color difference (Euclidean distance in RGB space)
        r_diff = abs(new_color.r - self._last_sent_color.r)
        g_diff = abs(new_color.g - self._last_sent_color.g)
        b_diff = abs(new_color.b - self._last_sent_color.b)
        a_diff = abs(new_color.a - self._last_sent_color.a)

        # Only send if change is significant (>5% in any channel)
        threshold = 0.05
        return (
            r_diff > threshold
            or g_diff > threshold
            or b_diff > threshold
            or a_diff > threshold
        )

    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up crystal light controller")

        # Stop speaking if active
        if self.is_speaking:
            await self.stop_speaking()

        # Cancel any running tasks
        if self.light_task and not self.light_task.done():
            self.light_task.cancel()
            try:
                await self.light_task
            except asyncio.CancelledError:
                pass

        # Close HTTP session
        if self.session:
            await self.session.close()
            self.session = None

    def get_status(self) -> Dict:
        """Get current status of the light controller"""
        return {
            "bot_config": self.bot_config,
            "connection_id": self.connection_id,
            "is_speaking": self.is_speaking,
            "current_color": {
                "r": self.current_color.r,
                "g": self.current_color.g,
                "b": self.current_color.b,
                "a": self.current_color.a,
            },
            "config": {
                "primary_color": {
                    "r": self.config.primary_color.r,
                    "g": self.config.primary_color.g,
                    "b": self.config.primary_color.b,
                    "a": self.config.primary_color.a,
                },
                "fade_to_color": {
                    "r": self.config.fade_to_color.r,
                    "g": self.config.fade_to_color.g,
                    "b": self.config.fade_to_color.b,
                    "a": self.config.fade_to_color.a,
                },
                "variation_intensity": self.config.variation_intensity,
                "color_shift_speed": self.config.color_shift_speed,
                "pulse_intensity": self.config.pulse_intensity,
                "pulse_speed": self.config.pulse_speed,
                "breathing_effect": self.config.breathing_effect,
                "breathing_speed": self.config.breathing_speed,
                "breathing_intensity": self.config.breathing_intensity,
            },
        }

    def get_light_command(self) -> Dict:
        """Get the current light command that should be sent to the client"""
        if not self.is_speaking:
            # When not speaking, send off color
            color = self.config.off_color
        else:
            # When speaking, send current animated color
            color = self.current_color

        red, green, blue, white = color.to_shelly_format()

        return {
            "type": "light_command",
            "bot_config": self.bot_config,
            "command": {
                "turn": "on" if color.a > 0 else "off",
                "mode": "color",
                "red": red,
                "green": green,
                "blue": blue,
                "white": white,
            },
            "shelly_ip": self.config.shelly_ip,
            "timestamp": time.time(),
        }
