"""
Live Microphone Audio Capture & Local Speech-to-Text Connector.

Features:
1. Continuous or single-shot audio capture from default microphone or earphones.
2. Low-latency local transcription using faster-whisper (tiny.en, ~200ms) with zero cloud dependencies.
3. Fallback to Google STT if requested or on whisper error.
4. Audio echo suppression: Automatically skips listening while Kokoro/afplay is speaking.
5. Direct integration with VoiceOSOrchestrator or remote HTTP daemon (http://127.0.0.1:8080/command).
"""

import sys
import os
import time
import subprocess
from typing import Dict, Any, Optional, Callable
import numpy as np
import speech_recognition as sr

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.settings import settings
from connectors.base import BaseConnector

class MicrophoneListener(BaseConnector):
    def __init__(
        self,
        engine: str = "faster_whisper",
        model_name: str = "tiny.en",
        device: str = "cpu",
        energy_threshold: int = 350,
        pause_threshold: float = 1.0,
        phrase_time_limit: float = 10.0,
        device_index: Optional[int] = None
    ):
        super().__init__(name="mic_listener")
        self.engine = engine
        self.model_name = model_name
        self.device = device
        self.energy_threshold = energy_threshold
        self.pause_threshold = pause_threshold
        self.phrase_time_limit = phrase_time_limit
        self.device_index = device_index

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = pause_threshold
        self.recognizer.non_speaking_duration = 0.5

        self._whisper_model = None
        self._is_running = False

    def connect(self) -> bool:
        """Initializes the STT model and verifies microphone access."""
        try:
            if self.engine == "faster_whisper":
                from faster_whisper import WhisperModel
                # int8 quantization on CPU or MPS for low memory & ultra-fast ~200ms execution
                self._whisper_model = WhisperModel(self.model_name, device=self.device, compute_type="int8")
            self._connected = True
            return True
        except Exception as e:
            print(f"[MicrophoneListener] Error connecting STT model: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._is_running = False
        self._connected = False

    def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "connected": self._connected,
            "engine": self.engine,
            "model_name": self.model_name,
            "whisper_loaded": self._whisper_model is not None,
            "available_mics": sr.Microphone.list_microphone_names()
        }

    def is_echo_playing(self) -> bool:
        """Checks if native macOS audio playback (afplay) is currently active to prevent echo."""
        try:
            res = subprocess.run(["pgrep", "-x", "afplay"], capture_output=True)
            return res.returncode == 0
        except Exception:
            return False

    def transcribe_audio_data(self, audio: sr.AudioData) -> str:
        """Converts AudioData to text using local faster-whisper or fallback."""
        if self.engine == "faster_whisper" and self._whisper_model is not None:
            try:
                # Direct in-memory PCM float32 array extraction (avoids av/ffmpeg container errors)
                raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                segments, _ = self._whisper_model.transcribe(audio_np, beam_size=1, language="en")
                text = " ".join([seg.text.strip() for seg in segments]).strip()
                return text
            except Exception as e:
                print(f"[MicrophoneListener] Faster-Whisper error: {e}. Trying Google STT...")

        # Fallback to Google STT
        try:
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            print(f"[MicrophoneListener] Fallback STT error: {e}")
            return ""

    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        """Captures a single utterance from the microphone."""
        if self.is_echo_playing():
            time.sleep(0.3)
            return None

        try:
            with sr.Microphone(device_index=self.device_index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=self.phrase_time_limit
                )
                text = self.transcribe_audio_data(audio)
                return text if text else None
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            print(f"[MicrophoneListener] Capture error: {e}")
            return None

    def start_listening_loop(
        self,
        callback: Callable[[str], None],
        poll_interval: float = 0.1
    ):
        """Continuously listens to microphone and invokes callback on recognized speech."""
        self._is_running = True
        print("[MicrophoneListener] Live listening loop started. Speak into your microphone...")
        with sr.Microphone(device_index=self.device_index) as source:
            print("[MicrophoneListener] Calibrating ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
            self.recognizer.energy_threshold = max(self.recognizer.energy_threshold, 350)
            print(f"[MicrophoneListener] Calibration complete (Threshold: {self.recognizer.energy_threshold:.0f}). Ready for voice commands.")

            while self._is_running:
                # Echo suppression
                if self.is_echo_playing():
                    time.sleep(0.3)
                    continue

                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=3.0,
                        phrase_time_limit=self.phrase_time_limit
                    )
                    # Don't transcribe if audio started playing while we were capturing
                    if self.is_echo_playing():
                        continue

                    text = self.transcribe_audio_data(audio)
                    if text and text.strip():
                        callback(text.strip())
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"[MicrophoneListener] Error in listen loop: {e}")
                    time.sleep(0.5)

    def stop_listening(self):
        self._is_running = False


def send_to_server(text: str, endpoint: str = "http://127.0.0.1:8080/command") -> Optional[Dict[str, Any]]:
    """Helper to send transcribed voice text to the local HTTP daemon."""
    import urllib.request
    import json

    try:
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[send_to_server Error] {e}")
        return None


if __name__ == "__main__":
    print("=" * 70)
    print(" Mac-Control Live Microphone STT Daemon")
    print(" Press Ctrl+C to stop.")
    print("=" * 70)

    listener = MicrophoneListener(
        engine=settings.stt.engine,
        model_name=settings.stt.whisper_model,
        device=settings.stt.device if settings.stt.device != "auto" else "cpu"
    )
    if not listener.connect():
        print("[Error] Failed to initialize STT listener.")
        exit(1)

    def on_voice_command(text: str):
        print(f"\n[Heard Voice]: '{text}'")
        res = send_to_server(text)
        if res:
            status = res.get("status")
            action = res.get("action") or res.get("message")
            tier = res.get("intent_tier", "direct")
            print(f"[Server Response] -> Status: {status} | Tier: {tier} | Action: {action}")
        else:
            print("[Server Response] -> Failed to reach daemon on http://127.0.0.1:8080")

    try:
        listener.start_listening_loop(callback=on_voice_command)
    except KeyboardInterrupt:
        print("\nStopping microphone listener.")
        listener.stop_listening()
