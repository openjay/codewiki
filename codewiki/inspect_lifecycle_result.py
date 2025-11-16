#!/usr/bin/env python3
"""
Inspect Code Wiki lifecycle classification results.

Quick utility to display key metrics and review recommendations
after running lifecycle classification.

Usage:
    python3 scripts/documentation/inspect_lifecycle_result.py
    python3 scripts/documentation/inspect_lifecycle_result.py --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_results(path: Path) -> Dict[str, Any]:
    """Load lifecycle recommendations JSON."""
    if not path.exists():
        print(f"❌ Results file not found: {path}", file=sys.stderr)
        print("   Run 'make code-wiki-lifecycle' first.", file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def print_metrics(data: Dict[str, Any], verbose: bool = False) -> None:
    """Print key metrics from lifecycle results."""
    meta = data.get("scan_metadata", {})
    summary = data.get("summary", {})

    print("=" * 70)
    print("CODE WIKI LIFECYCLE CLASSIFICATION - RESULTS")
    print("=" * 70)
    print()

    # Classification method
    method = meta.get("classification_method", "unknown")
    print(f"📋 Classification Method: {method}")

    if method == "llm-enhanced":
        print(f"   LLM Mode: {meta.get('llm_mode', 'N/A')}")
        print(
            f"   LLM Calls: {meta.get('llm_calls', 0)} / {meta.get('llm_max_files', 'unlimited')} max"
        )
        print()

        # LLM Parse Stats
        parse = meta.get("llm_parse", {})
        if parse:
            attempts = parse.get("attempts", 0)
            success = parse.get("parse_success", 0)
            failed = parse.get("parse_failed", 0)
            if attempts > 0:
                rate = success / attempts
                print(f"🔍 LLM Parse Statistics:")
                print(f"   Attempts: {attempts}")
                print(f"   Success:  {success} ({rate:.1%})")
                print(f"   Failed:   {failed} ({failed/attempts:.1%})")
                print()

        # LLM Stats
        stats = meta.get("llm_stats", {})
        if stats:
            attempts = stats.get("attempts", 0)
            successes = stats.get("successes", 0)
            fallbacks = stats.get("fallbacks", 0)
            print(f"🤖 LLM Performance:")
            print(f"   Attempts:  {attempts}")
            print(f"   Successes: {successes}")
            print(f"   Fallbacks: {fallbacks} (graceful degradation)")
            print()

        # Provider info
        usage = meta.get("llm_usage", {})
        if usage:
            print(f"⚙️  Provider:")
            print(f"   Provider: {usage.get('provider', 'N/A')}")
            print(f"   Model:    {usage.get('model', 'N/A')}")
            print(f"   Requests: {usage.get('total_requests', 0)}")
            print(f"   Tokens:   ~{usage.get('estimated_total_tokens', 0):,}")
            print(f"   Cost:     ${usage.get('cost', 0):.2f}")
            print()
    else:
        print()

    # Recommendations summary
    by_decision = summary.get("by_decision", {})
    total = summary.get("total_files", 0)

    print(f"📊 Recommendations ({total} files):")
    for decision in ["keep", "review", "archive", "delete"]:
        count = by_decision.get(decision, 0)
        if total > 0:
            pct = count / total * 100
            print(f"   {decision:8s}: {count:3d} ({pct:5.1f}%)")
        else:
            print(f"   {decision:8s}: {count:3d}")
    print()

    # Confidence distribution
    conf_dist = summary.get("confidence_distribution", {})
    if conf_dist:
        print("📈 Confidence Distribution:")
        for level, count in conf_dist.items():
            print(f"   {level:20s}: {count}")
        print()

    # Review files (always show)
    recs = data.get("recommendations", [])
    review_files = [r for r in recs if r.get("recommendation") == "review"]

    if review_files:
        print(f"🔎 FILES REQUIRING REVIEW ({len(review_files)}):")
        print("=" * 70)
        for r in review_files:
            print(f"\n📄 {r.get('path', 'N/A')}")
            print(f"   Confidence: {r.get('confidence', 0):.2f}")
            reasons = r.get("reasons", [])
            if reasons:
                print(f"   Reasons:")
                for reason in reasons:
                    print(f"      • {reason}")
            action = r.get("suggested_action")
            if action:
                print(f"   Action: {action}")
    else:
        print("✅ No files require review!")

    print()
    print("=" * 70)

    # Verbose mode: show archive/delete too
    if verbose:
        for decision in ["archive", "delete"]:
            decision_files = [r for r in recs if r.get("recommendation") == decision]
            if decision_files:
                print()
                print(f"📁 FILES MARKED FOR {decision.upper()} ({len(decision_files)}):")
                print("=" * 70)
                for r in decision_files:
                    print(f"\n📄 {r.get('path', 'N/A')}")
                    print(f"   Confidence: {r.get('confidence', 0):.2f}")
                    reasons = r.get("reasons", [])
                    if reasons:
                        print(f"   Reasons:")
                        for reason in reasons:
                            print(f"      • {reason}")
                print()
                print("=" * 70)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Inspect Code Wiki lifecycle classification results"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all recommendations (including archive/delete)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        default=Path("data/code_wiki/lifecycle_recommendations.json"),
        help="Path to lifecycle recommendations JSON (default: data/code_wiki/lifecycle_recommendations.json)",
    )

    args = parser.parse_args()

    data = load_results(args.file)
    print_metrics(data, verbose=args.verbose)

    return 0


if __name__ == "__main__":
    sys.exit(main())
