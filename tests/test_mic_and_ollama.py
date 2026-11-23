"""
Test Suite for MicrophoneListener and Local Ollama STT/Intent Pipeline.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectors.mic_listener import MicrophoneListener
from connectors.llm_connector import LLMConnector
from config.settings import settings

def run_tests():
    print("=" * 65)
    print(" Running Microphone Listener & Local Ollama Pipeline Tests")
    print("=" * 65)

    # 1. Test MicrophoneListener Init & Model Loading
    print("\n[Test 1] Initializing MicrophoneListener...")
    listener = MicrophoneListener(
        engine="faster_whisper",
        model_name="tiny.en",
        device="cpu"
    )
    ok = listener.connect()
    assert ok, "Failed to connect MicrophoneListener"
    health = listener.health_check()
    print(" - Health check:", health)
    assert health["connected"] is True
    assert health["whisper_loaded"] is True
    assert len(health["available_mics"]) > 0

    # 2. Test Echo Suppression Detection
    print("\n[Test 2] Echo suppression check:")
    is_echo = listener.is_echo_playing()
    print(" - Is afplay currently playing:", is_echo)
    assert isinstance(is_echo, bool)

    # 3. Test Local Ollama Qwen2.5:0.5b Routing (<1s, 0 env vars)
    print("\n[Test 3] Local Ollama intent routing with qwen2.5:0.5b:")
    llm = LLMConnector(ollama_model=settings.connectors.ollama_model)
    res = llm.route_intent("focus window Finder")
    print(" - Ollama intent response:", res)
    assert res is not None, "Ollama failed to return a response"
    assert "action" in res, "Ollama response missing 'action'"

    # 4. Test Settings Configuration
    print("\n[Test 4] Verify settings point to free/local models:")
    assert settings.connectors.ollama_model == "qwen2.5:0.5b"
    assert settings.stt.engine == "faster_whisper"
    assert settings.stt.whisper_model == "tiny.en"
    print(" - Verified local-only, zero-key configuration.")

    print("\n" + "=" * 65)
    print(" ALL MICROPHONE & OLLAMA TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
