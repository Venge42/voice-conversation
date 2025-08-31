"""
Audio configuration settings to prevent broken voice and improve audio quality.
"""

import os
from typing import Any, Dict

# Audio buffer settings to prevent broken voice
AUDIO_CONFIG = {
    # Buffer size settings (in samples)
    "buffer_size": 4096,  # Larger buffer for stability
    "sample_rate": 16000,  # Standard sample rate for speech
    "channels": 1,  # Mono audio for speech
    # VAD (Voice Activity Detection) settings
    "vad_threshold": 0.5,  # Sensitivity threshold
    "vad_min_speech_duration": 0.25,  # Minimum speech duration in seconds
    "vad_max_speech_duration": 30.0,  # Maximum speech duration in seconds
    # WebSocket settings
    "websocket_ping_interval": 30,  # Keep connection alive
    "websocket_ping_timeout": 10,
    "websocket_close_timeout": 5,
    # Audio processing settings
    "enable_audio_processing": True,
    "noise_reduction": True,
    "echo_cancellation": True,
    "auto_gain_control": True,
    # Connection retry settings
    "max_retry_attempts": 3,
    "retry_delay": 1000,  # milliseconds
    "connection_timeout": 30000,  # milliseconds
}


def get_audio_config() -> Dict[str, Any]:
    """Get audio configuration with environment variable overrides."""
    config = AUDIO_CONFIG.copy()

    # Allow environment variable overrides
    if os.getenv("AUDIO_BUFFER_SIZE"):
        config["buffer_size"] = int(os.getenv("AUDIO_BUFFER_SIZE"))

    if os.getenv("AUDIO_SAMPLE_RATE"):
        config["sample_rate"] = int(os.getenv("AUDIO_SAMPLE_RATE"))

    if os.getenv("VAD_THRESHOLD"):
        config["vad_threshold"] = float(os.getenv("VAD_THRESHOLD"))

    if os.getenv("WEBSOCKET_PING_INTERVAL"):
        config["websocket_ping_interval"] = int(os.getenv("WEBSOCKET_PING_INTERVAL"))

    return config


def get_websocket_params() -> Dict[str, Any]:
    """Get WebSocket-specific parameters for audio transport."""
    config = get_audio_config()

    return {
        "ping_interval": config["websocket_ping_interval"],
        "ping_timeout": config["websocket_ping_timeout"],
        "close_timeout": config["websocket_close_timeout"],
        "max_message_size": 1024 * 1024,  # 1MB max message size
        "compression": None,  # Disable compression for audio
    }


def get_audio_constraints() -> Dict[str, Any]:
    """Get audio constraints for getUserMedia."""
    config = get_audio_config()

    return {
        "audio": {
            "sampleRate": config["sample_rate"],
            "channelCount": config["channels"],
            "echoCancellation": config["echo_cancellation"],
            "noiseSuppression": config["noise_reduction"],
            "autoGainControl": config["auto_gain_control"],
            "latency": 0.01,  # Low latency for real-time communication
        }
    }
