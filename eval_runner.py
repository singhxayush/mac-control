#!/usr/bin/env python3
"""
Root Entry Point for Automated Evaluation & Benchmark Suite.

Usage:
  .venv/bin/python3 eval_runner.py
  .venv/bin/python3 eval_runner.py --category security_safety
  .venv/bin/python3 eval_runner.py --category app_controls
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from eval.eval_engine import EvalEngine

def main():
    parser = argparse.ArgumentParser(description="Mac-Control Automated Eval & Benchmark Suite")
    parser.add_argument("--category", type=str, default=None, help="Run a specific test category (e.g. security_safety, app_controls)")
    args = parser.parse_args()

    engine = EvalEngine()
    engine.run_benchmark(category=args.category)

if __name__ == "__main__":
    main()
