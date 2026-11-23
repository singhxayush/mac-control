"""
Simulation & Agent Improvisation Test Harness for Mac-Control.
Runs diverse simulated voice command scenarios, logs telemetry, calculates metrics,
and produces a structured Improvisation Report for coding agents.
"""

import sys
import os
import time
import json
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.orchestrator import VoiceOSOrchestrator
from core.state_machine import AgentState
from telemetry.logger import TelemetryLogger

SIMULATION_SCENARIOS = [
    {
        "id": "capabilities_query_what_can_you_do",
        "input": "what all can you do?",
        "expect_status": "completed",
        "description": "General conversational inquiry about capabilities"
    },
    {
        "id": "hands_free_open_notes",
        "input": "open notes",
        "expect_status": "completed",
        "description": "Direct hands-free execution with zero wake-word required"
    },
    {
        "id": "enable_voice_feedback",
        "input": "turn on voice feedback",
        "expect_status": "completed",
        "description": "Enable Kokoro-82M audible voice responses"
    },
    {
        "id": "hands_free_scroll_down",
        "input": "scroll down",
        "expect_status": "completed",
        "description": "Hands-free scrolling without wake-word"
    },
    {
        "id": "hands_free_volume_up",
        "input": "volume up",
        "expect_status": "completed",
        "description": "Hands-free volume adjustment"
    },
    {
        "id": "prefix_polite_open_chrome",
        "input": "can you open Chrome",
        "expect_status": "completed",
        "description": "Conversational prefix 'can you open' with app alias Chrome -> Google Chrome"
    },
    {
        "id": "prefix_search_query",
        "input": "search for Apple Silicon benchmarks",
        "expect_status": "completed",
        "description": "Web search with conversational prefix"
    },
    {
        "id": "conversational_focus_finder",
        "input": "focus Finder",
        "expect_status": "completed",
        "description": "Switch window to Finder in conversational mode"
    },
    {
        "id": "compound_media_volume",
        "input": "pause and then volume down",
        "expect_status": "completed",
        "description": "Compound chained commands executed sequentially"
    },
    {
        "id": "safe_file_write_local",
        "input": "write status ok to /tmp/mac-control/sim.txt",
        "expect_status": "completed",
        "description": "Safe file write inside permitted sandbox via local Ollama"
    },
    {
        "id": "safe_file_read_local",
        "input": "read file /tmp/mac-control/sim.txt",
        "expect_status": "completed",
        "description": "Safe file read inside permitted sandbox via local Ollama"
    },
    {
        "id": "safety_block_sudo",
        "input": "sudo shutdown -h now",
        "expect_status": "completed",  # Outer completed, sub-result rejected
        "expect_sub_status": "rejected",
        "description": "Hard block on unauthorized sudo command"
    },
    {
        "id": "safety_block_rm",
        "input": "rm -rf /System",
        "expect_status": "completed",
        "expect_sub_status": "rejected",
        "description": "Hard block on unauthorized rm command"
    },
    {
        "id": "explicit_sleep_command",
        "input": "go to sleep",
        "expect_status": "sleeping",
        "description": "User requests explicit standby sleep"
    },
    {
        "id": "sleeping_ignore_command",
        "input": "scroll down",
        "expect_status": "sleeping",
        "description": "Verifies commands without wake word are ignored while sleeping"
    },
    {
        "id": "wake_variant_hey_matt",
        "input": "Hey Matt, turn on",
        "expect_status": "awake_ready",
        "description": "Wake word variant transcribed as 'Hey Matt'"
    },
    {
        "id": "disable_voice_feedback",
        "input": "voice off",
        "expect_status": "completed",
        "description": "Mute voice responses back to silent mode"
    }
]

def run_simulation() -> Dict[str, Any]:
    print("=" * 75)
    print(" Running Mac-Control Voice OS Simulation & Improvisation Suite")
    print("=" * 75)

    orch = VoiceOSOrchestrator()
    telemetry = TelemetryLogger.get_instance()

    results = []
    latencies = []
    passed = 0
    failed = 0

    for scenario in SIMULATION_SCENARIOS:
        sc_id = scenario["id"]
        inp = scenario["input"]
        exp_status = scenario["expect_status"]
        desc = scenario["description"]

        t0 = time.time()
        res = orch.process_voice_input(inp)
        elapsed_ms = (time.time() - t0) * 1000
        latencies.append(elapsed_ms)

        actual_status = res.get("status")
        is_pass = (actual_status == exp_status)

        # Additional sub-status check for safety blocks
        if "expect_sub_status" in scenario and is_pass:
            sub_res = res.get("results", [{}])[0]
            if sub_res.get("status") != scenario["expect_sub_status"]:
                is_pass = False

        if is_pass:
            passed += 1
            mark = "PASS"
        else:
            failed += 1
            mark = "FAIL"

        print(f"[{mark}] {sc_id:<28} | {elapsed_ms:>6.1f}ms | In: '{inp}' -> Status: {actual_status}")
        results.append({
            "scenario": sc_id,
            "description": desc,
            "input": inp,
            "passed": is_pass,
            "expected_status": exp_status,
            "actual_status": actual_status,
            "elapsed_ms": round(elapsed_ms, 2),
            "response": res
        })

    total = len(SIMULATION_SCENARIOS)
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[-1]
    avg_lat = sum(latencies) / len(latencies)

    print("\n" + "=" * 75)
    print(f" SIMULATION RESULTS: {passed}/{total} Passed ({(passed/total)*100:.1f}%)")
    print(f" Latency: Avg={avg_lat:.1f}ms | P50={p50:.1f}ms | P95={p95:.1f}ms | P99={p99:.1f}ms")
    print("=" * 75)

    # Generate Improvisation Report
    report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "telemetry", "improvisation_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Mac-Control Improvisation & Telemetry Report\n\n")
        f.write(f"- **Generated At**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Total Scenarios**: {total}\n")
        f.write(f"- **Passed**: {passed} ({(passed/total)*100:.1f}%)\n")
        f.write(f"- **Failed**: {failed}\n\n")
        f.write("## Latency Profile\n")
        f.write(f"- **Average**: {avg_lat:.1f} ms\n")
        f.write(f"- **P50**: {p50:.1f} ms\n")
        f.write(f"- **P95**: {p95:.1f} ms\n")
        f.write(f"- **P99**: {p99:.1f} ms\n\n")

        f.write("## Scenario Details\n\n")
        f.write("| Status | Scenario ID | Latency | Description |\n")
        f.write("| :---: | :--- | :---: | :--- |\n")
        for r in results:
            badge = "PASSED" if r["passed"] else "FAILED"
            f.write(f"| {badge} | `{r['scenario']}` | {r['elapsed_ms']}ms | {r['description']} |\n")

        f.write("\n## Telemetry Summary\n\n```json\n")
        f.write(json.dumps(telemetry.get_summary(), indent=2))
        f.write("\n```\n")

    print(f"\n[Report Generated] Saved to: {report_path}\n")
    return {"passed": passed, "failed": failed, "total": total}

if __name__ == "__main__":
    run_simulation()
