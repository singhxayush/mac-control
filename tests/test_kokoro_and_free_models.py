"""
Kokoro-82M TTS & OpenRouter Free Models Security Policy Test Suite.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.orchestrator import VoiceOSOrchestrator
from connectors.llm_connector import LLMConnector
from connectors.tts_connector import TTSConnector

def run_tests():
    print("=" * 65)
    print(" Running Kokoro-82M & OpenRouter Free Models Policy Tests")
    print("=" * 65)

    orch = VoiceOSOrchestrator()

    # --- Test 1: Voice feedback is SILENT / DISABLED by default ---
    print("\n[Test 1] Verify voice feedback is disabled initially:")
    print(" - Initial voice_feedback_enabled:", orch.tts.voice_feedback_enabled)
    assert orch.tts.voice_feedback_enabled == False

    # Wake up the orchestrator
    orch.process_voice_input("Turn on")

    # --- Test 2: Toggle voice feedback ON via command ---
    print("\n[Test 2] Toggle voice feedback ON:")
    res = orch.process_voice_input("turn on voice feedback")
    print(" - Command result:", res["results"][0])
    assert orch.tts.voice_feedback_enabled == True
    assert res["results"][0]["status"] == "executed"

    # --- Test 3: Toggle voice feedback OFF via command ---
    print("\n[Test 3] Toggle voice feedback OFF:")
    res = orch.process_voice_input("voice off")
    print(" - Command result:", res["results"][0])
    assert orch.tts.voice_feedback_enabled == False
    assert res["results"][0]["status"] == "executed"

    # --- Test 4: OpenRouter Free Models Enforcement ---
    print("\n[Test 4] Verify OpenRouter Credit Protection Policy:")
    free_llm = LLMConnector(
        openrouter_api_key="test_key",
        openrouter_model="nvidia/llama-3.1-nemotron-70b-instruct:free",
        openrouter_free_only=True
    )
    health = free_llm.health_check()
    print(" - Free model configured:", health["openrouter_model"])
    assert health["openrouter_model"].endswith(":free")
    assert health["free_only_enforced"] == True

    # --- Test 5: Verify Non-Free Model is Hard-Blocked to Protect Credits ---
    print("\n[Test 5] Verify Paid Model Rejection:")
    paid_llm = LLMConnector(
        openrouter_api_key="test_key",
        openrouter_model="openai/gpt-4o",  # Paid model without :free tag
        openrouter_free_only=True
    )
    # Attempting to query should be rejected immediately before any network call
    res_paid = paid_llm._query_openrouter("test prompt")
    print(" - Paid model query result (should be None/rejected):", res_paid)
    assert res_paid is None

    # --- Test 6: Kokoro-82M Health Check ---
    print("\n[Test 6] Kokoro-82M TTS Health Check:")
    tts_health = orch.tts.health_check()
    print(" - TTS Health:", tts_health)
    assert tts_health["model"] == "Kokoro-82M"
    assert tts_health["voice"] == "af_heart"

    orch.shutdown()
    print("\n" + "=" * 65)
    print(" ALL KOKORO-82M & OPENROUTER FREE MODEL TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
