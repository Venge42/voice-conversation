#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import os
import sys

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

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


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


async def run_bot(websocket_client, bot_config=None, connection_id=None):
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

    # Configure bot based on selection
    if bot_config == "bot1":
        voice_id = "Puck"
        system_instruction = SYSTEM_INSTRUCTION
    elif bot_config == "bot2":
        voice_id = "Zephyr"
        system_instruction = (
            SYSTEM_INSTRUCTION
            + "\n\nDu bist eine alternative Version des Kristallwesens mit einer anderen Stimme."
        )
    else:
        voice_id = "Puck"
        system_instruction = SYSTEM_INSTRUCTION

    print(
        f"Using bot configuration: {bot_config}, voice: {voice_id}, connection: {connection_id}"
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
        logger.info("Pipecat client ready.")
        await rtvi.set_bot_ready()
        # Kick off the conversation.
        await task.queue_frames([LLMRunFrame()])

    @ws_transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Pipecat Client connected")

    @ws_transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Pipecat Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)
