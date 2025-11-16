#!/usr/bin/env python3
"""
CodeWiki CLI - Command-line interface for code lifecycle analysis.

Usage:
    codewiki --mode scan
    codewiki --mode lifecycle --profile weekly
    codewiki --mode docs
    codewiki --mode inspect --verbose
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

# Import orchestrator functions
from .orchestrator import main as orchestrator_main


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="codewiki",
        description="CodeWiki - LLM-enhanced code lifecycle analysis and documentation generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to Code Wiki configuration file (default: config/code_wiki_config.yaml)",
    )

    parser.add_argument(
        "--mode",
        choices=["scan", "lifecycle", "docs", "inspect"],
        default="lifecycle",
        help="Which Code Wiki workflow to run (default: lifecycle)",
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview changes without writing files (dry run)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--profile",
        choices=["daily", "weekly", "audit"],
        help="Use predefined operational profile (daily/weekly/audit)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Override llm_max_files limit (e.g., --limit 50 for quick scan)",
    )

    args = parser.parse_args()

    # Map CLI arguments to orchestrator arguments
    orch_args = []

    if args.config:
        orch_args.extend(["--config", str(args.config)])

    if args.mode:
        orch_args.extend(["--mode", args.mode])

    if args.preview:
        orch_args.append("--preview")

    if args.verbose:
        orch_args.append("--verbose")

    # For now, pass through to orchestrator
    # In future, profile/limit could modify config before calling orchestrator
    if args.profile:
        print(f"📋 Using profile: {args.profile}")
        print("   (Note: Modify config/code_wiki_config.yaml to adjust llm_max_files)")

    if args.limit:
        print(f"⚠️  --limit flag noted but not yet implemented")
        print(
            f"   Please modify config/code_wiki_config.yaml: llm_max_files: {args.limit}"
        )

    # Call orchestrator with mapped arguments
    sys.argv = ["codewiki"] + orch_args
    return orchestrator_main()


if __name__ == "__main__":
    sys.exit(main())
