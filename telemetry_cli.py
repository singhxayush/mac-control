#!/usr/bin/env python3
"""
Mac-Control Telemetry Analysis & Improvisation CLI.

Usage:
  .venv/bin/python3 telemetry_cli.py --summary
  .venv/bin/python3 telemetry_cli.py --tail -n 15
  .venv/bin/python3 telemetry_cli.py --failed
  .venv/bin/python3 telemetry_cli.py --export-eval data/telemetry/eval_dataset.json
  .venv/bin/python3 telemetry_cli.py --clear
"""

import sys
import os
import json
import argparse
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from telemetry.logger import TelemetryLogger

def print_banner():
    print("=" * 75)
    print("  Mac-Control: Local Telemetry & Agent Improvisation Dashboard")
    print("=" * 75)

def cmd_summary(logger: TelemetryLogger):
    print_banner()
    summary = logger.get_summary()
    total = summary.get("total_traces", 0)
    print(f"\n[Telemetry Overview] Log Path: {logger.log_path}")
    print(f" • Total Traces Captured : {total}")
    if total == 0:
        print("   (No traces recorded yet. Run commands to generate telemetry data.)\n")
        return

    print(f" • Successfully Executed : {summary.get('success_count', 0)} ({summary.get('success_rate_pct', 0.0)}%)")
    print(f" • Hard Blocked (Safety) : {summary.get('rejected_count', 0)}")
    print(f" • Confirmations Handled : {summary.get('confirmation_count', 0)}")
    print(f" • Unresolved Commands   : {summary.get('unresolved_count', 0)}")
    print(f" • Standby / Sleep Skips : {summary.get('sleeping_count', 0)}")

    lat = summary.get("latency", {})
    print(f"\n[Latency & SLA Performance] Target: <{lat.get('sla_target_ms', 2000):.0f}ms")
    print(f" • Average Latency       : {lat.get('average_ms', 0.0):.1f} ms")
    print(f" • P50 (Median) Latency  : {lat.get('p50_ms', 0.0):.1f} ms")
    print(f" • P95 Latency           : {lat.get('p95_ms', 0.0):.1f} ms")
    print(f" • P99 Latency           : {lat.get('p99_ms', 0.0):.1f} ms")
    print(f" • SLA Compliance Rate   : {lat.get('sla_compliant_pct', 0.0):.1f}% (<2.0s)")
    print(f" • Sub-Second Execution  : {lat.get('sub_second_pct', 0.0):.1f}% (<1.0s)")

    cost = summary.get("cost_metrics", {})
    print(f"\n[Cost Metric Determination]")
    print(f" • Actual Cost (USD)     : ${cost.get('actual_cost_usd', 0.0):.6f} (100% Free / On-Device)")
    print(f" • Total Tokens Processed: {cost.get('total_tokens_processed', 0)}")
    print(f" • Commercial API Saved  : ${cost.get('estimated_cloud_cost_saved_usd', 0.0):.6f} (vs Commercial Cloud APIs)")
    print(f" • Credit Protection     : Strict Free-Only Enforced")

    print("\n[Intent Tier Distribution]")
    for tier, count in summary.get("tier_distribution", {}).items():
        pct = (count / total) * 100
        print(f"   - {tier:<22}: {count:>4} ({pct:.1f}%)")
    print("=" * 75 + "\n")

def cmd_spans(logger: TelemetryLogger, trace_id: str):
    print_banner()
    traces = logger.read_traces()
    matched = [t for t in traces if t.get("trace_id", "").startswith(trace_id)]
    if not matched:
        print(f"\nNo trace found matching prefix '{trace_id}'.\n")
        return

    t = matched[-1]
    print(f"\n[Trace Details] ID: {t.get('trace_id')} at {t.get('iso_time')}")
    print(f" • Input      : '{t.get('raw_input')}'")
    print(f" • Normalized : '{t.get('normalized_input')}'")
    print(f" • State      : {t.get('agent_state_before')} -> {t.get('agent_state_after')}")
    print(f" • Tier       : {t.get('tier_name')}")
    print(f" • Status     : {t.get('status')}")
    print(f" • Total Time : {t.get('latency_ms', {}).get('total', 0.0):.1f} ms")
    print(f" • Spoken     : {t.get('spoken_feedback')}")

    cost = t.get("cost", {})
    print(f" • Cost USD   : ${cost.get('cost_usd', 0.0):.6f} (Provider: {cost.get('compute_provider', 'local')})")

    spans = t.get("spans", [])
    print(f"\n[Distributed Execution Waterfall] ({len(spans)} Spans):")
    if not spans:
        print("   (No individual sub-spans recorded for this trace)")
    else:
        for i, s in enumerate(spans, 1):
            dur = s.get("duration_ms", 0.0)
            meta = s.get("metadata", {})
            meta_str = f" | {meta}" if meta else ""
            print(f"   [{i}] {s.get('name'):<25} : {dur:>6.1f}ms (Status: {s.get('status')}){meta_str}")
    print("\n" + "=" * 75 + "\n")

def cmd_tail(logger: TelemetryLogger, n: int = 15):
    print_banner()
    traces = logger.read_traces(limit=n)
    if not traces:
        print("\nNo traces found.\n")
        return

    print(f"\nShowing Last {len(traces)} Recorded Traces:\n")
    header = f"{'Trace ID':<10} | {'Input Text':<28} | {'Tier':<14} | {'Status':<14} | {'Latency':<8}"
    print(header)
    print("-" * len(header))
    for t in traces:
        tid = t.get("trace_id", "")[:8]
        inp = (t.get("raw_input") or "")[:26]
        tier = t.get("tier_name", "unknown")[:13]
        status = t.get("status", "unknown")[:13]
        lat = f"{t.get('latency_ms', {}).get('total', 0.0):.0f}ms"
        print(f"{tid:<10} | {inp:<28} | {tier:<14} | {status:<14} | {lat:<8}")
    print("\n" + "=" * 75 + "\n")

def cmd_failed(logger: TelemetryLogger):
    print_banner()
    traces = logger.read_traces()
    failed = [t for t in traces if t.get("status") in ["unresolved", "error"] or t.get("error")]
    print(f"\n[Failure & Unresolved Analysis] Found {len(failed)} issues:\n")
    if not failed:
        print("  All recorded traces executed cleanly with zero unhandled failures!\n")
        return

    for i, t in enumerate(failed, 1):
        print(f"[{i}] Trace ID: {t.get('trace_id')} at {t.get('iso_time')}")
        print(f"    Raw Input  : '{t.get('raw_input')}'")
        print(f"    Normalized : '{t.get('normalized_input')}'")
        print(f"    State      : {t.get('agent_state_before')} -> {t.get('agent_state_after')}")
        print(f"    Tier Tried : {t.get('tier_name')}")
        print(f"    Status     : {t.get('status')}")
        if t.get("error"):
            print(f"    Error Log  : {t.get('error')}")
        print(f"    Action Tried: {t.get('action_payload')}")
        print("-" * 60)
    print("\n" + "=" * 75 + "\n")

def cmd_export_eval(logger: TelemetryLogger, output_path: str):
    traces = logger.read_traces()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(traces, f, indent=2)
    print(f"[Export] Saved {len(traces)} traces to benchmark evaluation dataset: {output_path}")

def cmd_clear(logger: TelemetryLogger):
    if os.path.exists(logger.log_path):
        os.remove(logger.log_path)
    print(f"[Clear] Reset telemetry trace log at {logger.log_path}")

def main():
    parser = argparse.ArgumentParser(description="Mac-Control Telemetry & Improvisation CLI")
    parser.add_argument("--summary", action="store_true", help="Print telemetry overview, SLA and cost metrics")
    parser.add_argument("--tail", action="store_true", help="Display recent traces")
    parser.add_argument("-n", "--limit", type=int, default=15, help="Number of traces to tail (default 15)")
    parser.add_argument("--failed", action="store_true", help="Display only unresolved/failed traces for agent analysis")
    parser.add_argument("--spans", type=str, metavar="TRACE_ID", help="Display execution waterfall spans for a trace")
    parser.add_argument("--export-eval", type=str, metavar="PATH", help="Export traces to JSON for simulation benchmarks")
    parser.add_argument("--clear", action="store_true", help="Clear all stored telemetry traces")

    args = parser.parse_args()
    logger = TelemetryLogger.get_instance()

    if args.summary:
        cmd_summary(logger)
    elif args.spans:
        cmd_spans(logger, args.spans)
    elif args.tail:
        cmd_tail(logger, n=args.limit)
    elif args.failed:
        cmd_failed(logger)
    elif args.export_eval:
        cmd_export_eval(logger, args.export_eval)
    elif args.clear:
        cmd_clear(logger)
    else:
        cmd_summary(logger)

if __name__ == "__main__":
    main()
