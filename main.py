#!/usr/bin/env python3
"""
Mac-Control CLI Entry Point with Live Microphone STT Support.

Usage:
  .venv/bin/python3 main.py           # Interactive keyboard input mode
  .venv/bin/python3 main.py --mic     # Live continuous microphone listening + keyboard mode
"""

import sys
import os
import threading

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.orchestrator import VoiceOSOrchestrator
from connectors.mic_listener import MicrophoneListener
from config.settings import settings

def main():
    enable_mic = "--mic" in sys.argv or "-m" in sys.argv

    print("=" * 70)
    print("  Mac-Control: Voice OS Agent (Clean OOP Architecture)")
    print("=" * 70)
    print(" Lifecycle State:")
    print("  • Wake Words: 'Hey Mac', 'Mac', 'Turn on', 'Wake up'")
    print("  • Sleep Words: 'Go to sleep', 'Turn off', 'Standby'")
    print("  • Auto-Sleep: 45s idle timeout (releases browser memory & CPU)")
    print("  • Safety: Zero sudo, zero permanent rm, macOS Trash only")
    print(f"  • Microphone Input: {'ENABLED (Listening continuously)' if enable_mic else 'DISABLED (Use --mic to enable)'}")
    print("  • Audio Output (TTS): DISABLED / SILENT by default ('voice on' to toggle)")
    print("=" * 70)
    print("\n[Status] System initialized in SLEEPING / STANDBY mode.")
    print("Try saying or typing: 'Hey Mac, scroll down' or 'Turn on'\n")

    orch = VoiceOSOrchestrator()
    listener = None

    if enable_mic:
        listener = MicrophoneListener(
            engine=settings.stt.engine,
            model_name=settings.stt.whisper_model,
            device=settings.stt.device if settings.stt.device != "auto" else "cpu"
        )
        if listener.connect():
            def on_voice_detected(text: str):
                print(f"\n[Microphone Heard]: '{text}'")
                res = orch.process_voice_input(text)
                print(f"[Voice Result]: {res}\n[{orch.lifecycle.current_state.value.upper()}] Voice > ", end="", flush=True)

            mic_thread = threading.Thread(
                target=listener.start_listening_loop,
                args=(on_voice_detected,),
                daemon=True,
                name="MicListenerThread"
            )
            mic_thread.start()
        else:
            print("[Warning] Could not initialize live microphone listener.")

    try:
        while True:
            try:
                prompt_state = orch.lifecycle.current_state.value.upper()
                user_input = input(f"[{prompt_state}] Voice > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    break

                result = orch.process_voice_input(user_input)
                print(f"[Response] {result}\n")

            except (KeyboardInterrupt, EOFError):
                break
    finally:
        if listener:
            listener.stop_listening()
        orch.shutdown()

if __name__ == "__main__":
    main()
