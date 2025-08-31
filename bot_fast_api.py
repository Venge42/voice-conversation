#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import os
import sys
import threading
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

from lore_loader import (
    create_enhanced_system_prompt,
    load_lore_files,
    print_prompt_sizes,
)

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


async def run_bot(websocket_client, bot_config=None, connection_id=None):
    # Get connection-specific logger
    conn_logger = get_connection_logger(connection_id)

    try:
        conn_logger.info(
            f"Starting bot session for config: {bot_config}, connection: {connection_id}"
        )

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
            model="models/gemini-2.5-flash-preview-native-audio-dialog",  # Use the same model as websocket server
            language="de-DE",
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

        # RTVI events for Pipecat client UI
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        pipeline = Pipeline(
            [
                ws_transport.input(),
                context_aggregator.user(),
                rtvi,
                llm,  # LLM
                ws_transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi)],
        )

        @rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            conn_logger.info("Pipecat client ready - starting conversation")
            await rtvi.set_bot_ready()
            # Kick off the conversation.
            await task.queue_frames([LLMRunFrame()])

        @ws_transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            conn_logger.info("Pipecat Client connected")

        @ws_transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            conn_logger.info("Pipecat Client disconnected - cleaning up")
            try:
                await task.cancel()
            except Exception as e:
                conn_logger.error(f"Error during task cancellation: {e}")

        @ws_transport.event_handler("on_error")
        async def on_transport_error(transport, error):
            conn_logger.error(f"Transport error: {error}")

        runner = PipelineRunner(handle_sigint=False)

        conn_logger.info("Starting pipeline runner")
        await runner.run(task)

    except asyncio.CancelledError:
        conn_logger.info("Bot session cancelled")
        raise
    except Exception as e:
        conn_logger.error(f"Unexpected error in run_bot: {e}")
        raise
    finally:
        conn_logger.info("Bot session cleanup complete")
