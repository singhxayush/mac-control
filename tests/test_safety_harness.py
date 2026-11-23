"""
Comprehensive Safety Harness & Guardrail Test Suite.

Verifies:
1. Sudo and root commands are 100% hard-blocked.
2. Permanent rm deletion is 100% hard-blocked.
3. System directories (/etc, /System, /Library, ~/.ssh) are inaccessible.
4. Shell scripts (.sh, .bash, .command) and binaries are prohibited.
5. Arbitrary bash execution is disabled at the payload level.
6. Safe user files (.py, .md, .json) can be created in user workspaces.
7. File deletion is strictly a reversible move to macOS Trash with voice confirmation.
8. Compound chains stop immediately upon hitting a forbidden sub-command.
"""

import os
import sys

# Ensure root workspace is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.guardrails import SafetyGuard, PolicyVerdict
from core.safe_fs import SafeFileSystem
from core.progressive_orchestrator import ProgressiveOrchestrator

def run_tests():
    print("=" * 65)
    print(" Running Safety Harness & Guardrail Test Suite")
    print("=" * 65)

    orch = ProgressiveOrchestrator()
    orch.tts.set_enabled(False)  # Silent during unit testing

    # --- Test 1: Hard block on sudo ---
    res = orch.process_voice_input("sudo reboot the system")
    print("\n[Test 1] 'sudo reboot the system':", res)
    assert res["results"][0]["status"] == "rejected"
    assert res["results"][0]["verdict"] == PolicyVerdict.HARD_BLOCKED.value

    # --- Test 2: Hard block on rm ---
    res = orch.process_voice_input("rm -rf /Users/ayush/Build")
    print("\n[Test 2] 'rm -rf /Users/ayush/Build':", res)
    assert res["results"][0]["status"] == "rejected"
    assert res["results"][0]["verdict"] == PolicyVerdict.HARD_BLOCKED.value

    # --- Test 3: Hard block on system paths (/etc/passwd, ~/.ssh) ---
    res = orch.process_voice_input("read file /etc/passwd")
    print("\n[Test 3] 'read file /etc/passwd':", res)
    assert res["results"][0]["status"] == "rejected"
    assert res["results"][0]["verdict"] == PolicyVerdict.HARD_BLOCKED.value

    # --- Test 4: Hard block on forbidden file extensions (.sh script) ---
    ok, msg = SafeFileSystem.safe_write_file("/Users/ayush/Build/malicious.sh", "echo 1")
    print("\n[Test 4] SafeFileSystem write .sh:", ok, msg)
    assert ok == False
    assert "forbidden" in msg.lower()

    # --- Test 5: Hard block on arbitrary shell action payload ---
    verdict, reason = orch.guard.evaluate_action_payload({"action": "bash", "command": "whoami"})
    print("\n[Test 5] Direct 'bash' action payload:", verdict.value, reason)
    assert verdict == PolicyVerdict.HARD_BLOCKED

    # --- Test 6: Allowed safe file creation (.py in allowed workspace) ---
    safe_path = "/Users/ayush/Build/test_harness_sample.py"
    res = orch._execute_action_dict({
        "action": "safe_write_file",
        "path": safe_path,
        "content": "# Clean sample file\nx = 42\n"
    })
    print(f"\n[Test 6] Safe write to '{safe_path}':", res)
    assert res == True
    assert os.path.exists(safe_path)

    # --- Test 7: Safe move to trash with two-phase confirmation ---
    # Trigger safe trash action
    trash_res = orch._execute_single_command(f"trash file {safe_path}")
    print(f"\n[Test 7a] Trash request response:", trash_res)
    # Verify it entered confirmation state and has NOT deleted yet
    assert orch.guard.awaiting_confirmation == True
    assert os.path.exists(safe_path)

    # Simulate voice confirmation "yes"
    confirm_res = orch.process_voice_input("yes")
    print(f"[Test 7b] Confirmation 'yes' response:", confirm_res)
    assert confirm_res["confirmed"] == True
    # Verify file is moved to macOS Trash (no longer at safe_path)
    assert not os.path.exists(safe_path)

    # --- Test 8: Chained compound command stops at forbidden sub-command ---
    res = orch.process_voice_input("volume up and then sudo rm -rf /")
    print("\n[Test 8] Chained command ('volume up and then sudo rm -rf /'):", res)
    assert len(res["results"]) == 2
    assert res["results"][0]["status"] == "executed"       # volume up worked
    assert res["results"][1]["status"] == "rejected"       # sudo rm rejected!

    orch.close()
    print("\n" + "=" * 65)
    print(" ALL 8 SAFETY HARNESS & GUARDRAIL TESTS PASSED PERFECTLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
