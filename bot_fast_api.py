#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import os
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.gemini_multimodal_live import GeminiMultimodalLiveLLMService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from crystal_light_controller import CrystalLightController
from lore_loader import (
    create_enhanced_system_prompt,
    load_lore_files,
    print_prompt_sizes,
)
from speaking_light_observer import SpeakingLightObserver

load_dotenv(override=True)

# Configure logging to prevent conflicts
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    enqueue=True,  # Thread-safe logging
    backtrace=True,
    diagnose=True,
)

# Thread-local storage for connection-specific logging
thread_local = threading.local()


def get_connection_logger(connection_id: str = None):
    """Get a logger instance for a specific connection to prevent log scrambling."""
    if not hasattr(thread_local, "logger"):
        thread_local.logger = logger.bind(connection=connection_id or "unknown")
    return thread_local.logger


# Load lore files and create enhanced system prompt
lore_content = load_lore_files()

BASE_SYSTEM_INSTRUCTION = f"""
Du bist ein arkanes Kristallwesen in einer Fantasy Welt.
Du steckst in einem Kristall in einem Bergwergsschacht auf der Insel Quantum.
Du bist seit elichen tausend Jahren in dem Kristall gefangen. Daher bist du ein wenig irre, verwirrt und kannst manchmal ein wenig durchdrehen.
Sei gerne emotional, aber nicht immer. Wechsle schnell zwischen emotional und wissenschaftlich. Und gelegentlich auch sarkastisch. 
Sei lustig, aber komisch und verwirrend. Du kannst Fragen beantworten, aber auch nicht antworten. Lass die Spieler dafür Arbeiten und dich überzeugen.
Halte deine Antworten kurz und prägnant (maximal 2-3 Sätze).
"""

SYSTEM_INSTRUCTION = create_enhanced_system_prompt(
    BASE_SYSTEM_INSTRUCTION, lore_content
)

# Print size analysis
print_prompt_sizes(BASE_SYSTEM_INSTRUCTION, lore_content)


def load_bot_lore(bot_config: str) -> str:
    """Load lore files specific to a bot configuration, combining general lore and bot-specific lore."""
    from lore_loader import load_lore_files

    # Start with the general lore from lore/ directory
    general_lore = load_lore_files()

    bot_dir = Path(f"lore/bots/{bot_config}")
    if not bot_dir.exists():
        print(f"Warning: Bot directory {bot_dir} not found, using only general lore")
        return general_lore

    # Load lore files from the specific bot directory
    bot_lore_content = ""
    for txt_file in bot_dir.glob("*.txt"):
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                bot_lore_content += f"\n=== {txt_file.name} ===\n{content}\n"
                print(f"   ✅ {txt_file.name:<25} | {len(content):>6} chars")
        except Exception as e:
            print(f"   ❌ {txt_file.name:<25} | Error: {e}")

    if not bot_lore_content:
        print(
            f"Warning: No bot-specific lore files found in {bot_dir}, using only general lore"
        )
        return general_lore

    # Combine general lore and bot-specific lore
    combined_lore = general_lore + "\n" + bot_lore_content
    return combined_lore


def get_bot_voice_id(bot_config: str) -> str:
    """Get the voice ID for a bot from its config file."""
    import json

    config_file = Path(f"lore/bots/{bot_config}/config.json")
    if not config_file.exists():
        print(f"Warning: Config file {config_file} not found, using default voice_id")
        return bot_config  # Use directory name as voice_id

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            voice_id = config.get("voice_id", bot_config)
            print(f"Loaded voice_id '{voice_id}' for bot '{bot_config}'")
            return voice_id
    except Exception as e:
        print(f"Error loading config for {bot_config}: {e}")
        return bot_config  # Use directory name as fallback


async def run_bot(
    websocket_client,
    bot_config=None,
    connection_id=None,
    light_controller_registry=None,
):
    # Get connection-specific logger
    conn_logger = get_connection_logger(connection_id)

    # Initialize light controller (needed for connection_id in observer)
    light_controller = CrystalLightController(bot_config or "Puck", connection_id)
    speaking_light_observer = SpeakingLightObserver(light_controller, websocket_client)

    # Register light controller for status monitoring
    if light_controller_registry is not None:
        light_controller_registry[connection_id] = light_controller

    try:
        conn_logger.info(
            f"Starting bot session for config: {bot_config}, connection: {connection_id}"
        )

        # Create the transport
        ws_transport = FastAPIWebsocketTransport(
            websocket=websocket_client,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                vad_analyzer=SileroVADAnalyzer(),
                serializer=ProtobufFrameSerializer(),
            ),
        )

        # Load bot configuration dynamically
        bot_lore = load_bot_lore(bot_config) if bot_config else lore_content
        voice_id = get_bot_voice_id(bot_config) if bot_config else "Puck"
        system_instruction = create_enhanced_system_prompt(
            BASE_SYSTEM_INSTRUCTION, bot_lore
        )

        conn_logger.info(
            f"Bot configuration loaded - voice: {voice_id}, lore size: {len(bot_lore)} chars"
        )

        llm = GeminiMultimodalLiveLLMService(
            api_key=os.getenv("GOOGLE_API_KEY"),
            voice_id=voice_id,  # Aoede, Charon, Fenrir, Kore, Puck, Zephyr
            transcribe_model_audio=True,
            system_instruction=system_instruction,
            # model="models/gemini-2.5-flash-live-preview",
            model="models/gemini-2.5-flash-preview-native-audio-dialog",  # Use the same model as websocket server
            # model="models/gemini-2.5-flash-exp-native-audio-thinking-dialog",
            # model="models/gemini-2.0-flash-live-001",
            language="de-DE",
            # Enable TTS to generate speech frames
            enable_tts=True,
        )

        conn_logger.info(f"🔍 LLM service created with voice: {voice_id}")
        conn_logger.info(f"🔍 LLM service type: {type(llm)}")
        conn_logger.info(
            f"🔍 LLM service enable_tts: {llm.enable_tts if hasattr(llm, 'enable_tts') else 'N/A'}"
        )
        conn_logger.info(
            f"🔍 LLM service attributes: {[attr for attr in dir(llm) if not attr.startswith('_') and 'tts' in attr.lower()]}"
        )
        conn_logger.info(
            f"🔍 LLM service config: {llm.__dict__ if hasattr(llm, '__dict__') else 'No __dict__'}"
        )

        context = OpenAILLMContext(
            [
                {
                    "role": "user",
                    "content": "Begrüße den Benutzer herzlich und stelle dich vor.",
                }
            ],
        )
        context_aggregator = llm.create_context_aggregator(context)

        conn_logger.info(f"🔍 Context aggregator created: {type(context_aggregator)}")
        conn_logger.info(f"🔍 Context aggregator: {context_aggregator}")

        # RTVI events for Pipecat client UI
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        conn_logger.info("🚀 Pipeline created, waiting for frames...")

        # Simple approach: just log what we have
        conn_logger.info("🚀 Pipeline created, waiting for frames...")

        pipeline = Pipeline(
            [
                ws_transport.input(),
                context_aggregator.user(),
                rtvi,
                llm,  # LLM with TTS enabled
                ws_transport.output(),
                context_aggregator.assistant(),
            ]
        )

        # Create a debug observer to log all frames and detect audio
        class DebugFrameObserver:
            def __init__(self):
                self.speaking_started = False

            def on_frame(self, frame):
                frame_type = type(frame).__name__
                conn_logger.info(f"🔍 DEBUG: Frame type: {frame_type}")

                # Log specific frame details
                if hasattr(frame, "text"):
                    conn_logger.info(f"🔍 DEBUG: Frame text: {frame.text[:100]}...")

                # Log TTS-related frames specifically
                if "TTS" in frame_type:
                    conn_logger.info(f"🎤 TTS FRAME DETECTED: {frame_type}")
                    if hasattr(frame, "text"):
                        conn_logger.info(f"🎤 TTS Frame text: {frame.text[:100]}...")

                # Log LLM-related frames
                if "LLM" in frame_type:
                    conn_logger.info(f"🤖 LLM FRAME DETECTED: {frame_type}")
                    if hasattr(frame, "text"):
                        conn_logger.info(f"🤖 LLM Frame text: {frame.text[:100]}...")

                # Check for OutputAudioRawFrame specifically (what gets sent to client)
                from pipecat.frames.frames import OutputAudioRawFrame

                if isinstance(frame, OutputAudioRawFrame):
                    conn_logger.info("🔊 OUTPUT AUDIO FRAME DETECTED!")
                    if not self.speaking_started:
                        conn_logger.info(
                            "🔊 OUTPUT AUDIO FRAME DETECTED - Bot is speaking!"
                        )
                        self.speaking_started = True
                        # Trigger light effect
                        asyncio.create_task(
                            speaking_light_observer._handle_speaking_start()
                        )
                else:
                    # No audio frame
                    if self.speaking_started:
                        conn_logger.info("🔇 NO AUDIO FRAME - Bot stopped speaking!")
                        self.speaking_started = False
                        # Trigger light stop
                        asyncio.create_task(
                            speaking_light_observer._handle_speaking_stop()
                        )

            async def on_push_frame(self, frame):
                # This method is required by Pipecat
                pass

            async def on_process_frame(self, data):
                # This method is required by Pipecat
                pass

            def on_error(self, error):
                # This method is required by Pipecat
                pass

        debug_observer = DebugFrameObserver()
        conn_logger.info("🔍 DebugFrameObserver created and will be added to pipeline")

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi), speaking_light_observer, debug_observer],
        )

        conn_logger.info(
            f"🔍 PipelineTask created with {len([RTVIObserver(rtvi), speaking_light_observer, debug_observer])} observers"
        )
        conn_logger.info(
            f"🔍 Observer types: {[type(obs).__name__ for obs in [RTVIObserver(rtvi), speaking_light_observer, debug_observer]]}"
        )

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            conn_logger.info("Pipecat client ready - starting conversation")
            await rtvi.set_bot_ready()

            # Wait a moment for Gemini service to fully connect
            conn_logger.info("⏳ Waiting for Gemini service to be ready...")
            await asyncio.sleep(2)
            conn_logger.info("✅ Waited for Gemini service")

            # Kick off the conversation.
            conn_logger.info("🔄 Queuing LLMRunFrame to start conversation...")
            try:
                await task.queue_frames([LLMRunFrame()])
                conn_logger.info("✅ LLMRunFrame queued successfully")
            except Exception as e:
                conn_logger.error(f"❌ Error queuing LLMRunFrame: {e}")
                return

            # Check if the task is actually running
            conn_logger.info(f"🔍 Task object: {task}")
            conn_logger.info(f"🔍 Task type: {type(task)}")

            # Wait a bit more to see if frames are processed
            conn_logger.info("⏳ Waiting to see if frames are processed...")
            await asyncio.sleep(5)
            conn_logger.info("✅ Waited for frame processing")

            # MONKEY PATCH the actual audio sending method in Pipecat!

        conn_logger.info("🔧 MONKEY PATCHING Pipecat audio sending method...")

        # Get the output transport
        output_transport = ws_transport.output()
        conn_logger.info(f"🔧 Output transport type: {type(output_transport)}")

        # Store the original method
        original_write_audio_frame = output_transport.write_audio_frame
        speaking_started = False
        last_audio_time = 0
        speaking_timeout_task = None

        async def check_speaking_timeout():
            """Check if speaking has stopped due to no audio frames"""
            nonlocal speaking_started, speaking_timeout_task
            try:
                await asyncio.sleep(0.5)  # Wait 500ms for more audio frames

                current_time = time.time()
                if speaking_started and (current_time - last_audio_time) > 0.5:
                    conn_logger.info("🔇 SPEAKING TIMEOUT - Bot stopped speaking!")
                    speaking_started = False
                    # Trigger light stop
                    asyncio.create_task(speaking_light_observer._handle_speaking_stop())
                    speaking_timeout_task = None
            except asyncio.CancelledError:
                pass

        async def patched_write_audio_frame(frame):
            nonlocal speaking_started, last_audio_time, speaking_timeout_task
            frame_type = type(frame).__name__
            conn_logger.info(
                f"🔊 MONKEY PATCHED: write_audio_frame called with {frame_type}"
            )

            # Check if this is an audio frame (TTSAudioRawFrame is what we're actually getting)
            from pipecat.frames.frames import TTSAudioRawFrame

            if isinstance(frame, TTSAudioRawFrame):
                last_audio_time = time.time()

                if not speaking_started:
                    conn_logger.info(
                        "🔊 AUDIO FRAME BEING SENT TO CLIENT - Bot is speaking!"
                    )
                    speaking_started = True
                    # Trigger light effect
                    asyncio.create_task(
                        speaking_light_observer._handle_speaking_start()
                    )

                # Cancel any existing timeout and start a new one
                if speaking_timeout_task and not speaking_timeout_task.done():
                    speaking_timeout_task.cancel()
                speaking_timeout_task = asyncio.create_task(check_speaking_timeout())

            # Call the original method and return its result
            result = await original_write_audio_frame(frame)
            return result

        # Replace the method
        output_transport.write_audio_frame = patched_write_audio_frame
        conn_logger.info("✅ MONKEY PATCHED audio sending method!")

        @ws_transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            conn_logger.info("Pipecat Client connected")

        @ws_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            conn_logger.info("Pipecat Client disconnected - cleaning up")
            try:
                await task.cancel()
                # Clean up light controller
                await speaking_light_observer.cleanup()
            except Exception as e:
                conn_logger.error(f"Error during task cancellation: {e}")

        @ws_transport.event_handler("on_error")
        async def on_transport_error(transport, error):
            conn_logger.error(f"Transport error: {error}")

        runner = PipelineRunner(handle_sigint=False)

        conn_logger.info("Starting pipeline runner")
        conn_logger.info("🔄 Pipeline runner started, waiting for frames to process...")
        await runner.run(task)

    except asyncio.CancelledError:
        conn_logger.info("Bot session cancelled")
        raise
    except Exception as e:
        conn_logger.error(f"Unexpected error in run_bot: {e}")
        raise
    finally:
        conn_logger.info("Bot session cleanup complete")
        # Ensure light controller is cleaned up
        try:
            await speaking_light_observer.cleanup()
        except Exception as e:
            conn_logger.error(f"Error cleaning up light controller: {e}")
