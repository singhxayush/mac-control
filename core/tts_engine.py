"""
Text-to-Speech (TTS) Engine - SILENT & MUTED BY DEFAULT.

Audio playback is strictly disabled (GLOBAL_MUTE = True) to prevent any
unexpected speech. All speech events are logged to the console silently.
"""

import os

# GLOBAL SAFETY OVERRIDE: Zero audio output without explicit user opt-in.
GLOBAL_MUTE = True

class TTSEngine:
    def __init__(self, backend="silent", voice="gentle", default_enabled=False):
        self.backend = backend
        self.voice = voice
        self.enabled = default_enabled and not GLOBAL_MUTE

    def set_enabled(self, enabled: bool):
        # Even if enabled is passed, GLOBAL_MUTE enforces strict silence
        if GLOBAL_MUTE:
            self.enabled = False
            print("[TTS Engine] Audio remains strictly MUTED by safety override.")
            return
        self.enabled = enabled

    def speak(self, text: str, force: bool = False, async_speak: bool = True):
        """
        Logs the message silently to console.
        ZERO audio will be played while GLOBAL_MUTE is True.
        """
        print(f"[TTS (Muted)] '{text}'")

        if GLOBAL_MUTE or not self.enabled:
            return

        # Audio playback code is intentionally disabled
        pass
