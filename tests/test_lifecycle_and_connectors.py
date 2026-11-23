"""
Lifecycle, Wake-Word, and Connector Pattern Test Suite.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.orchestrator import VoiceOSOrchestrator
from core.state_machine import AgentState
from events.lifecycle_events import WakeWordDetectedEvent, StateTransitionEvent
from connectors.browser_connector import BrowserConnector

def run_tests():
    print("=" * 65)
    print(" Running Lifecycle, Wake-Word & Connector Architecture Tests")
    print("=" * 65)

    orch = VoiceOSOrchestrator()

    # --- Test 1: Starts in SLEEPING mode and ignores commands without wake-word ---
    print("\n[Test 1] Initial state check:")
    assert orch.lifecycle.current_state == AgentState.SLEEPING
    res = orch.process_voice_input("scroll down")
    print(" - Input while sleeping ('scroll down'):", res["status"])
    assert res["status"] == "sleeping"

    # --- Test 2: Wake-Word activation ('Hey Mac, scroll down') ---
    print("\n[Test 2] Wake-word activation with compound command:")
    res = orch.process_voice_input("Hey Mac, scroll down and then volume up")
    print(" - Response:", res)
    assert orch.lifecycle.current_state == AgentState.AWAKE_ACTIVE
    assert res["status"] == "completed"
    assert len(res["commands"]) == 2

    # --- Test 3: Commands execute directly while AWAKE ---
    print("\n[Test 3] Direct command while awake:")
    res = orch.process_voice_input("pause")
    print(" - Direct reflex response:", res["results"][0]["status"])
    assert res["results"][0]["status"] == "executed"

    # --- Test 4: Explicit sleep command ('Go to sleep') ---
    print("\n[Test 4] Explicit sleep command:")
    res = orch.process_voice_input("Go to sleep")
    print(" - Response:", res)
    assert orch.lifecycle.current_state == AgentState.SLEEPING

    # --- Test 5: Verify sleeping state ignores input again ---
    res = orch.process_voice_input("volume down")
    print(" - Sleeping check ('volume down'):", res["status"])
    assert res["status"] == "sleeping"

    # --- Test 6: Wake-up via 'Turn on' ---
    res = orch.process_voice_input("Turn on")
    print("\n[Test 6] 'Turn on' wake activation:", res["status"])
    assert orch.lifecycle.current_state == AgentState.AWAKE_ACTIVE

    # --- Test 7: Simulated idle timeout auto-sleep ---
    print("\n[Test 7] Idle timeout simulation:")
    # Set last active time to 50 seconds in the past (timeout is 45s)
    orch.lifecycle.last_active_time = time.time() - 50.0
    timeout_triggered = orch.lifecycle.check_idle_timeout()
    print(" - Idle timeout triggered:", timeout_triggered)
    assert timeout_triggered == True
    assert orch.lifecycle.current_state == AgentState.SLEEPING

    # --- Test 8: Browser Connector Lifecycle Disconnect on Sleep ---
    print("\n[Test 8] Browser connector lifecycle test:")
    browser_conn = BrowserConnector(cdp_port=9222)
    browser_conn.disconnect()
    health = browser_conn.health_check()
    print(" - Health check after disconnect:", health)
    assert health["connected"] == False
    assert health["page_active"] == False

    orch.shutdown()
    print("\n" + "=" * 65)
    print(" ALL 8 LIFECYCLE, WAKE-WORD & CONNECTOR TESTS PASSED!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
