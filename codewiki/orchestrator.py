#!/usr/bin/env python3
"""
Code Wiki Orchestrator

Scope:
- Single entrypoint for all Code Wiki operations
- PR #1: Repository scanning
- PR #2: Lifecycle classification
- PR #3: Documentation generation

Available Modes:
- scan: Run full scan and write index to disk
- check: Run scan and print summary only (no disk writes)
- lifecycle: Run lifecycle classifier on existing index
- docgen: Generate documentation from index and lifecycle data

Future Modes (v1.1+):
- full-refresh: Scan + classify + generate all docs in one command
- incremental: Only update changed files based on ledger
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Import modules
from . import doc_generator, lifecycle_classifier, repo_scanner


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Code Wiki Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full scan and write index
  python scripts/documentation/code_wiki_orchestrator.py --mode scan

  # Check scan results without writing
  python scripts/documentation/code_wiki_orchestrator.py --mode check

  # Run lifecycle classification
  python scripts/documentation/code_wiki_orchestrator.py --mode lifecycle

  # Preview lifecycle classification without writing
  python scripts/documentation/code_wiki_orchestrator.py --mode lifecycle --preview

  # Generate documentation
  python scripts/documentation/code_wiki_orchestrator.py --mode docgen

  # Preview documentation generation
  python scripts/documentation/code_wiki_orchestrator.py --mode docgen --preview

  # Or use Makefile shortcuts
  make code-wiki-scan
  make code-wiki-check
  make code-wiki-lifecycle
  make code-wiki-docgen
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["scan", "check", "lifecycle", "docgen"],
        default="scan",
        help="Operation mode: scan, check, lifecycle, or docgen",
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: show what would be done without writing files",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/code_wiki_config.yaml",
        help="Path to Code Wiki config file",
    )

    return parser.parse_args()


def run_scan(write_to_disk: bool = True) -> int:
    """
    Run repository scan.

    Args:
        write_to_disk: If True, write index to disk. If False, only print summary.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    config_path = REPO_ROOT / "config" / "code_wiki_config.yaml"

    if not config_path.exists():
        print(f"❌ [code-wiki] Config not found: {config_path}", file=sys.stderr)
        return 1

    try:
        # Load config
        config = repo_scanner.load_code_wiki_config(config_path)

        # Run scan
        print(f"🔍 [code-wiki] Scanning repository from {REPO_ROOT}...")
        index = repo_scanner.scan_repository(config)
        index_dict = repo_scanner.repo_index_to_dict(index)

        meta = index.scan_metadata

        if write_to_disk:
            # Write mode: save index to disk
            output_path = REPO_ROOT / config.get("output", {}).get(
                "index_path", "data/code_wiki/repo_index.json"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w", encoding="utf-8") as f:
                json.dump(index_dict, f, ensure_ascii=False, indent=2)

            print(f"✅ [code-wiki] Scan complete!")
            print(f"📊 Files scanned: {meta['files_scanned']}")
            print(f"⏱️  Duration: {meta['duration_seconds']}s")
            print(f"📝 Output: {output_path}")
            print(
                f"🔗 Git commit: {meta['git_commit'][:8] if meta['git_commit'] != 'unknown' else 'unknown'}"
            )

        else:
            # Check mode: only print summary
            print(f"✅ [code-wiki] Scan (check mode) complete:")
            print(f"  Files scanned : {meta['files_scanned']}")
            print(f"  Duration (s)  : {meta['duration_seconds']}")
            print(f"  Timestamp     : {meta['timestamp']}")
            print(
                f"  Git commit    : {meta['git_commit'][:8] if meta['git_commit'] != 'unknown' else 'unknown'}"
            )
            print()

            # Print breakdown by file kind
            kind_counts = {}
            for file_entry in index.files:
                kind = file_entry.kind
                kind_counts[kind] = kind_counts.get(kind, 0) + 1

            print("  File breakdown:")
            for kind in sorted(kind_counts.keys()):
                count = kind_counts[kind]
                print(f"    {kind:12s}: {count:5d} files")

        return 0

    except Exception as e:
        print(
            f"❌ [code-wiki] Error during scan ({type(e).__name__}): {e}",
            file=sys.stderr,
        )
        return 1


def run_lifecycle(config: dict, preview: bool = False) -> int:
    """
    Run lifecycle classification.

    Args:
        config: Code Wiki configuration
        preview: If True, only show what would be done without writing

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Get paths from config
    index_path = REPO_ROOT / config.get("output", {}).get(
        "index_path", "data/code_wiki/repo_index.json"
    )
    lifecycle_output = REPO_ROOT / config.get("output", {}).get(
        "lifecycle_path", "data/code_wiki/lifecycle_recommendations.json"
    )

    # Check if index exists
    if not index_path.exists():
        print(
            f"❌ [code-wiki] Repo index not found at {index_path}",
            file=sys.stderr,
        )
        print(
            "   Run 'make code-wiki-scan' or '--mode scan' first.",
            file=sys.stderr,
        )
        return 1

    # Get lifecycle config (V1.2 enhanced)
    lifecycle_cfg = config.get("lifecycle_classifier", {})
    deprecation_days = int(lifecycle_cfg.get("deprecation_days", 90))
    confidence_threshold = float(lifecycle_cfg.get("confidence_threshold", 0.7))
    use_llm = bool(lifecycle_cfg.get("use_llm", False))  # V1.1+
    llm_mode = lifecycle_cfg.get("llm_mode", "full")  # V1.2
    llm_max_files = lifecycle_cfg.get("llm_max_files")  # V1.2
    
    # V2.0: Environment variable overrides for validation/benchmarking
    import os
    if os.environ.get("CODEWIKI_USE_LIR") == "true":
        use_llm = True  # LIR requires LLM to be enabled
        llm_mode = "lir"  # Signal to use LIR
    elif os.environ.get("CODEWIKI_USE_LIR") == "false":
        # Force legacy client (disable LIR)
        os.environ["CODEWIKI_DISABLE_LIR"] = "true"
    if os.environ.get("CODEWIKI_LIR_POLICY"):
        llm_mode = os.environ.get("CODEWIKI_LIR_POLICY", llm_mode)
    if os.environ.get("CODEWIKI_LLM_MAX_FILES"):
        llm_max_files = int(os.environ.get("CODEWIKI_LLM_MAX_FILES"))

    # V1.2: Print LLM status
    if use_llm:
        print(
            f"🤖 [code-wiki] LLM enhancement ENABLED (mode={llm_mode}, max_files={llm_max_files})"
        )

    try:
        # Run classification
        lifecycle_classifier.run_lifecycle_classification(
            index_path=index_path,
            output_path=lifecycle_output,
            deprecation_days=deprecation_days,
            confidence_threshold=confidence_threshold,
            dry_run=preview,
            use_llm=use_llm,  # V1.1+
            llm_mode=llm_mode,  # V1.2
            llm_max_files=llm_max_files,  # V1.2
        )
        return 0

    except Exception as e:
        print(
            f"❌ [code-wiki] Error during lifecycle classification ({type(e).__name__}): {e}",
            file=sys.stderr,
        )
        return 1


def run_docgen(config: dict, preview: bool = False) -> int:
    """
    Run documentation generation.

    Args:
        config: Code Wiki configuration
        preview: If True, only show what would be generated without writing

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Get paths from config
    index_path = REPO_ROOT / config.get("output", {}).get(
        "index_path", "data/code_wiki/repo_index.json"
    )
    lifecycle_path = REPO_ROOT / config.get("output", {}).get(
        "lifecycle_path", "data/code_wiki/lifecycle_recommendations.json"
    )

    # Check if index exists
    if not index_path.exists():
        print(
            f"❌ [code-wiki] Repo index not found at {index_path}",
            file=sys.stderr,
        )
        print(
            "   Run 'make code-wiki-scan' or '--mode scan' first.",
            file=sys.stderr,
        )
        return 1

    # Get doc generator config
    docgen_cfg = config.get("doc_generator", {})
    output_dir = REPO_ROOT / docgen_cfg.get("output_dir", "docs/architecture")
    update_readme = docgen_cfg.get("update_readme", False)
    readme_path = REPO_ROOT / "README.md" if update_readme else None

    try:
        # Run documentation generation
        doc_generator.run_doc_generation(
            index_path=index_path,
            lifecycle_path=lifecycle_path if lifecycle_path.exists() else None,
            output_dir=output_dir,
            readme_path=readme_path,
            preview=preview,
        )
        return 0

    except Exception as e:
        print(
            f"❌ [code-wiki] Error during documentation generation ({type(e).__name__}): {e}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Load config
    config_path = REPO_ROOT / args.config
    if not config_path.exists():
        print(f"❌ [code-wiki] Config not found: {config_path}", file=sys.stderr)
        return 1

    try:
        config = repo_scanner.load_code_wiki_config(config_path)
    except Exception as e:
        print(
            f"❌ [code-wiki] Failed to load config ({type(e).__name__}): {e}",
            file=sys.stderr,
        )
        return 1

    # Route to appropriate handler
    if args.mode in ("scan", "check"):
        write_to_disk = args.mode == "scan" and not args.preview
        return run_scan(write_to_disk=write_to_disk)
    elif args.mode == "lifecycle":
        return run_lifecycle(config=config, preview=args.preview)
    elif args.mode == "docgen":
        return run_docgen(config=config, preview=args.preview)
    else:
        print(f"❌ [code-wiki] Unknown mode: {args.mode}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
