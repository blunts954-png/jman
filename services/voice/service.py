"""
Voice Service - STT and TTS for Jarvis
"""
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("jarvis.voice")

# Try to import optional dependencies
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Whisper not available - STT disabled")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logger.warning("pyttsx3 not available - TTS disabled")


class VoiceService:
    """Voice I/O service for STT and TTS"""
    
    def __init__(self):
        self.config = None
        self._stt_model = None
        self._tts_engine = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize voice service"""
        if self._initialized:
            return
        
        from core.config import get_config
        self.config = get_config().voice
        
        # Load STT model
        if WHISPER_AVAILABLE:
            try:
                logger.info(f"Loading Whisper model: {self.config.stt_model}")
                self._stt_model = whisper.load_model(self.config.stt_model)
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                self._stt_model = None
        
        # Initialize TTS engine
        if PYTTSX3_AVAILABLE:
            try:
                self._tts_engine = pyttsx3.init()
                logger.info("TTS engine initialized")
            except Exception as e:
                logger.error(f"Failed to initialize TTS: {e}")
                self._tts_engine = None
        
        self._initialized = True
    
    async def transcribe(
        self,
        audio_data: Optional[bytes] = None,
        audio_path: Optional[str] = None
    ) -> str:
        """
        Transcribe audio to text using Whisper
        
        Args:
            audio_data: Raw audio bytes
            audio_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        await self.initialize()
        
        if self._stt_model is None:
            raise RuntimeError("STT model not available")
        
        # Handle audio input
        if audio_path:
            # Load from file
            result = self._stt_model.transcribe(audio_path)
            return result["text"].strip()
        
        elif audio_data:
            # Write to temp file and transcribe
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_data)
                temp_path = f.name
            
            try:
                result = self._stt_model.transcribe(temp_path)
                return result["text"].strip()
            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)
        
        else:
            raise ValueError("Either audio_data or audio_path must be provided")
    
    async def speak(
        self,
        text: str,
        voice_id: Optional[str] = None,
        rate: int = 200,
        volume: int = 100
    ) -> float:
        """
        Synthesize speech from text
        
        Args:
            text: Text to speak
            voice_id: Voice ID (optional)
            rate: Speech rate
            volume: Volume level
            
        Returns:
            Duration of speech in seconds
        """
        await self.initialize()
        
        if self._tts_engine is None:
            raise RuntimeError("TTS engine not available")
        
        # Configure TTS properties
        self._tts_engine.setProperty('rate', rate)
        self._tts_engine.setProperty('volume', volume / 100.0)
        
        if voice_id:
            voices = self._tts_engine.getProperty('voices')
            for voice in voices:
                if voice.id == voice_id:
                    self._tts_engine.setProperty('voice', voice.id)
                    break
        
        # Run TTS in executor to not block
        loop = asyncio.get_event_loop()
        
        # Get approximate duration (words per minute)
        words = len(text.split())
        duration = (words / (rate / 60)) if rate > 0 else 3.0
        
        def _speak():
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        
        await loop.run_in_executor(None, _speak)
        
        return duration
    
    async def listen_for_wake_word(self) -> bool:
        """
        Listen for wake word (placeholder - would need actual implementation)
        
        Returns:
            True if wake word detected
        """
        # This would need a proper wake word detection implementation
        # For now, return False
        return False
    
    async def capture_audio(self, duration: float = 5.0) -> bytes:
        """
        Capture audio from microphone
        
        Args:
            duration: Duration in seconds
            
        Returns:
            Audio bytes
        """
        # This would need proper audio capture implementation
        # For now, return empty bytes
        return b""


# Singleton instance
_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    """Get voice service singleton"""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
