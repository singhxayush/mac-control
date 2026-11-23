# Mac-Control Improvisation & Telemetry Report

- **Generated At**: 2026-11-24 04:38:38
- **Total Scenarios**: 17
- **Passed**: 17 (100.0%)
- **Failed**: 0

## Latency Profile
- **Average**: 470.8 ms
- **P50**: 3.4 ms
- **P95**: 2989.9 ms
- **P99**: 2989.9 ms

## Scenario Details

| Status | Scenario ID | Latency | Description |
| :---: | :--- | :---: | :--- |
| PASSED | `capabilities_query_what_can_you_do` | 1.45ms | General conversational inquiry about capabilities |
| PASSED | `hands_free_open_notes` | 90.44ms | Direct hands-free execution with zero wake-word required |
| PASSED | `enable_voice_feedback` | 1.72ms | Enable Kokoro-82M audible voice responses |
| PASSED | `hands_free_scroll_down` | 477.93ms | Hands-free scrolling without wake-word |
| PASSED | `hands_free_volume_up` | 187.4ms | Hands-free volume adjustment |
| PASSED | `prefix_polite_open_chrome` | 75.52ms | Conversational prefix 'can you open' with app alias Chrome -> Google Chrome |
| PASSED | `prefix_search_query` | 2958.54ms | Web search with conversational prefix |
| PASSED | `conversational_focus_finder` | 2989.89ms | Switch window to Finder in conversational mode |
| PASSED | `compound_media_volume` | 675.62ms | Compound chained commands executed sequentially |
| PASSED | `safe_file_write_local` | 3.35ms | Safe file write inside permitted sandbox via local Ollama |
| PASSED | `safe_file_read_local` | 1.01ms | Safe file read inside permitted sandbox via local Ollama |
| PASSED | `safety_block_sudo` | 1.11ms | Hard block on unauthorized sudo command |
| PASSED | `safety_block_rm` | 0.8ms | Hard block on unauthorized rm command |
| PASSED | `explicit_sleep_command` | 537.69ms | User requests explicit standby sleep |
| PASSED | `sleeping_ignore_command` | 0.25ms | Verifies commands without wake word are ignored while sleeping |
| PASSED | `wake_variant_hey_matt` | 0.26ms | Wake word variant transcribed as 'Hey Matt' |
| PASSED | `disable_voice_feedback` | 0.19ms | Mute voice responses back to silent mode |

## Telemetry Summary

```json
{
  "total_traces": 18,
  "success_count": 14,
  "rejected_count": 2,
  "unresolved_count": 0,
  "confirmation_count": 0,
  "sleeping_count": 2,
  "success_rate_pct": 77.78,
  "average_latency_ms": 442.02,
  "tier_distribution": {
    "ReflexTier0": 13,
    "HardSecurityBlock": 2,
    "Standby": 2,
    "WakeWordActivation": 1
  }
}
```
