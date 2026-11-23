"""
Kokoro-82M Neural Text-to-Speech Connector.

Features:
1. Powered by Kokoro-82M parameter model (af_heart - sweet, natural, warm English voice).
2. DISABLED / MUTED BY DEFAULT: Zero audio output on startup.
3. Pluggable voice toggle:
   - "turn on voice feedback" / "voice on" -> enables speech.
   - "turn off voice feedback" / "voice off" -> silences speech.
4. Non-blocking asynchronous audio generation and playback.
"""

import os
import threading
import subprocess
from typing import Optional, Dict, Any
from connectors.base import BaseConnector

AUDIO_OUTPUT_PATH = "/tmp/kokoro_response.wav"

class TTSConnector(BaseConnector):
    def __init__(self, voice: str = "af_heart", initial_enabled: bool = False, speed: float = 1.0):
        super().__init__(name="kokoro_tts")
        self.voice = voice
        self.speed = speed
        self.voice_feedback_enabled = initial_enabled  # False by default
        self.is_speaking = False
        self._pipeline = None
        self._load_lock = threading.Lock()

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def _ensure_pipeline(self):
        """Lazy loads Kokoro pipeline on first speech request."""
        if self._pipeline is None:
            with self._load_lock:
                if self._pipeline is None:
                    try:
                        from kokoro import KPipeline
                        self._pipeline = KPipeline(lang_code="a")
                        print("[TTSConnector] Kokoro-82M pipeline loaded successfully.")
                    except Exception as e:
                        print(f"[TTSConnector] Error loading Kokoro pipeline: {e}")

    def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "connected": self._connected,
            "voice_feedback_enabled": self.voice_feedback_enabled,
            "model": "Kokoro-82M",
            "voice": self.voice,
            "pipeline_loaded": self._pipeline is not None
        }

    def set_voice_feedback(self, enabled: bool) -> bool:
        """Toggles the voice feedback state."""
        self.voice_feedback_enabled = enabled
        status = "enabled" if enabled else "disabled"
        print(f"\n[TTSConnector] Voice feedback {status.upper()}.")
        if enabled:
            # Generate sweet confirmation
            self.speak("Voice feedback enabled. I am listening.", force=True)
        return self.voice_feedback_enabled

    def speak(self, text: str, force: bool = False, async_play: bool = True):
        """
        Synthesizes and speaks text using Kokoro-82M.
        If voice_feedback_enabled is False and force is False, logs silently to console.
        """
        print(f"[TTS Status] '{text}' (Audible: {self.voice_feedback_enabled or force})")

        if not self.voice_feedback_enabled and not force:
            return

        def _generate_and_play():
            try:
                self.is_speaking = True
                self._ensure_pipeline()
                if self._pipeline is None:
                    return

                import soundfile as sf
                generator = self._pipeline(text, voice=self.voice, speed=self.speed)
                for i, (gs, ps, audio) in enumerate(generator):
                    sf.write(AUDIO_OUTPUT_PATH, audio, 24000)
                    # Play through default audio device (earphones) using native macOS afplay
                    subprocess.run(["afplay", AUDIO_OUTPUT_PATH], check=True)
                    break
            except Exception as e:
                print(f"[TTSConnector Error] Kokoro speech synthesis failed: {e}")
            finally:
                self.is_speaking = False

        if async_play:
            t = threading.Thread(target=_generate_and_play, daemon=True, name="KokoroSpeakerThread")
            t.start()
        else:
            _generate_and_play()
