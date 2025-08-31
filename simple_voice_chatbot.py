import asyncio
import os

import dotenv
import numpy as np
import pyaudio
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMTextFrame, TranscriptionFrame, TTSAudioRawFrame
from pipecat.observers.base_observer import BaseObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response import LLMAssistantResponseAggregator
from pipecat.processors.aggregators.sentence import SentenceAggregator
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.google.stt import GoogleSTTService
from pipecat.services.google.tts import GoogleTTSService
from pipecat.transports.local.audio import (
    LocalAudioInputTransport,
    LocalAudioOutputTransport,
    LocalAudioTransportParams,
)

# Load environment variables
load_dotenv()


class ChatbotObserver(BaseObserver):
    """Observer to track pipeline events and print status"""

    def on_frame(self, frame):
        print(f"📡 Frame received: {type(frame).__name__}")
        if isinstance(frame, TranscriptionFrame):
            if frame.text:
                print(f"🎤 Transcribed: '{frame.text}'")
            else:
                print("🎤 Transcribing...")
        elif isinstance(frame, LLMTextFrame):
            print(f"🤖 AI Response: '{frame.text}'")
        elif isinstance(frame, TTSAudioRawFrame):
            print("🔊 Playing audio response...")

    def on_error(self, error):
        print(f"❌ Error: {error}")


async def main():
    # Initialize services with optimized settings for minimal latency
    vad = SileroVADAnalyzer(
        sample_rate=16000,
        params=VADParams(
            confidence=0.5,
            start_secs=0.2,  # Reduced for faster response
            stop_secs=0.05,  # Reduced for faster response
            min_volume=0.6,
        ),
    )
    print("✅ VAD initialized")

    stt = GoogleSTTService(
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        language="en-US",
        model="latest_long",
        use_enhanced=True,
    )
    print("✅ Google STT service initialized")

    llm = GoogleLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model="gemini-1.5-flash",
        system_prompt="You are a helpful and friendly AI assistant. Keep responses concise and natural for voice conversation. Respond in 1-2 sentences maximum. Be conversational and engaging.",
        temperature=0.7,
        max_tokens=150,
    )
    print("✅ Google LLM service initialized")

    tts = GoogleTTSService(
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        voice="en-US-Neural2-F",
        language="en-US",
        speaking_rate=1.0,
        pitch=0.0,
    )
    print("✅ Google TTS service initialized")

    print("🔧 Creating pipeline...")
    # Create pipeline with direct audio I/O for minimal latency
    pipeline = Pipeline(
        [
            # Microphone input with optimized settings
            LocalAudioInputTransport(
                py_audio=pyaudio.PyAudio(),
                params=LocalAudioTransportParams(
                    audio_in_enabled=True,
                    audio_in_sample_rate=16000,
                    audio_in_channels=1,
                    audio_in_stream_on_start=True,
                    audio_in_passthrough=True,
                    audio_out_enabled=True,
                    audio_out_sample_rate=16000,
                    audio_out_channels=1,
                    vad_enabled=True,
                    vad_analyzer=vad,
                ),
            ),
            # Voice Activity Detection (integrated in transport)
            # Speech to Text
            stt,
            # Sentence aggregation
            SentenceAggregator(),
            # LLM processing
            llm,
            # LLM response aggregation
            LLMAssistantResponseAggregator(),
            # Text to Speech
            tts,
            # Speaker output
            LocalAudioOutputTransport(
                py_audio=pyaudio.PyAudio(),
                params=LocalAudioTransportParams(
                    audio_out_enabled=True,
                    audio_out_sample_rate=16000,
                    audio_out_channels=1,
                ),
            ),
        ]
    )
    print("✅ Pipeline created successfully")

    print("Starting voice chatbot...")
    print("Speak to interact with the AI assistant!")
    print("Press Ctrl+C to exit")

    # Run pipeline with observer
    runner = PipelineRunner()
    observer = ChatbotObserver()
    task = PipelineTask(pipeline, observers=[observer])
    await runner.run(task)


if __name__ == "__main__":
    dotenv.load_dotenv()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down voice chatbot...")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have set up your .env file with the required credentials:")
        print("- GOOGLE_API_KEY (for Gemini LLM)")
        print(
            "- GOOGLE_APPLICATION_CREDENTIALS (path to service account JSON for STT/TTS)"
        )
