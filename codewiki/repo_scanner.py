#!/usr/bin/env python3
"""
Repository scanner for the Code Wiki system.

V1 Responsibilities (PR #1):
- Load scan configuration from code_wiki_config.yaml
- Walk the repository under include_paths
- Apply exclude_patterns
- Build a lightweight index of files:
    - path
    - kind (python/config/test/script/doc/other)
    - basic stats (size, mtime)
- Return a Python dict; orchestrator is responsible for writing to disk.

Note: Ledger tracking (file_ledger.jsonl) will be added in PR #2 with lifecycle logic.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../longter


@dataclass
class FileEntry:
    """Metadata for a single file in the repository."""

    path: str
    kind: str  # python/config/test/script/doc/other
    size_bytes: int
    mtime: float  # POSIX timestamp
    language: Optional[str] = None
    is_test: bool = False


@dataclass
class RepoIndex:
    """Complete repository index with metadata."""

    scan_metadata: Dict
    files: List[FileEntry]


def load_code_wiki_config(config_path: Path) -> dict:
    """Load Code Wiki configuration from YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_git_commit() -> str:
    """Get current git commit hash. Returns 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return "unknown"


def _matches_any_pattern(path: Path, patterns: Iterable[str]) -> bool:
    """Return True if path (as posix string) matches any glob pattern."""
    s = path.as_posix()
    return any(fnmatch.fnmatch(s, pattern) for pattern in patterns)


def _classify_file(path: Path) -> FileEntry:
    """
    Classify a file and extract basic metadata.

    V1: Simple heuristics based on file extension and path.
    Future: Can be extended with AST parsing for Python files.
    """
    rel_path = path.relative_to(REPO_ROOT).as_posix()
    stat = path.stat()
    size = stat.st_size
    mtime = stat.st_mtime

    suffix = path.suffix.lower()
    language = None
    kind = "other"
    is_test = False

    # Classify based on extension and path
    if suffix == ".py":
        language = "python"
        # Check if it's a test file (more precise detection)
        test_indicators = [
            rel_path.startswith("tests/"),
            rel_path.startswith("test_"),
            "/test_" in rel_path,
            rel_path.endswith("_test.py"),
        ]
        if any(test_indicators):
            is_test = True
            kind = "test"
        elif rel_path.startswith("scripts/"):
            kind = "script"
        else:
            kind = "python"

    elif suffix in {".yml", ".yaml"}:
        kind = "config"
        language = "yaml"

    elif suffix == ".json":
        kind = "config"
        language = "json"

    elif suffix == ".md":
        kind = "doc"
        language = "markdown"

    elif suffix in {".sh", ".bash"}:
        kind = "script"
        language = "bash"

    elif suffix in {".ts", ".tsx"}:
        language = "typescript"
        kind = "typescript"

    elif suffix in {".js", ".jsx"}:
        language = "javascript"
        kind = "javascript"

    elif suffix == ".toml":
        kind = "config"
        language = "toml"

    elif suffix in {".txt", ".log"}:
        kind = "doc"

    else:
        kind = "other"

    return FileEntry(
        path=rel_path,
        kind=kind,
        size_bytes=size,
        mtime=mtime,
        language=language,
        is_test=is_test,
    )


def scan_repository(config: dict) -> RepoIndex:
    """
    Scan the repository and build a file index.

    Args:
        config: Configuration dictionary from code_wiki_config.yaml

    Returns:
        RepoIndex with scan metadata and file entries
    """
    scan_cfg = config.get("scan_settings", {})
    include_paths = scan_cfg.get("include_paths", [])
    exclude_patterns = scan_cfg.get("exclude_patterns", [])

    start_ts = time.time()
    files: List[FileEntry] = []

    # Scan each included path
    for inc in include_paths:
        root = (REPO_ROOT / inc).resolve()
        if not root.exists():
            # Skip if path doesn't exist (graceful handling)
            continue

        # Recursively walk directory
        # TODO(v1.1): Optimize to prune excluded directories before descending.
        # Currently rglob() visits all dirs then filters files. Works correctly
        # and fast (0.018s for 661 files), but could be optimized using os.walk()
        # with directory pruning for repos with large node_modules/ or .venv/.
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            # Check exclusion patterns
            rel = path.relative_to(REPO_ROOT)
            if _matches_any_pattern(rel, exclude_patterns):
                continue

            # Classify and add to index
            try:
                entry = _classify_file(path)
                files.append(entry)
            except (OSError, PermissionError):
                # Skip files we can't read
                continue

    end_ts = time.time()

    # Build metadata
    scan_metadata = {
        "project_root": str(REPO_ROOT),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end_ts)),
        "git_commit": _get_git_commit(),
        "duration_seconds": round(end_ts - start_ts, 3),
        "files_scanned": len(files),
        "config_version": config.get("version", "unknown"),
    }

    return RepoIndex(scan_metadata=scan_metadata, files=files)


def repo_index_to_dict(index: RepoIndex) -> dict:
    """Convert RepoIndex to JSON-serializable dictionary."""
    return {
        "scan_metadata": index.scan_metadata,
        "files": [asdict(f) for f in index.files],
    }


def main() -> None:
    """Main entry point for standalone execution."""
    config_path = REPO_ROOT / "config" / "code_wiki_config.yaml"

    if not config_path.exists():
        raise SystemExit(f"❌ Config not found: {config_path}")

    # Load config and scan
    config = load_code_wiki_config(config_path)
    print(f"🔍 Scanning repository from {REPO_ROOT}...")

    index = scan_repository(config)
    index_dict = repo_index_to_dict(index)

    # Write output
    output_path = REPO_ROOT / config.get("output", {}).get(
        "index_path", "data/code_wiki/repo_index.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(index_dict, f, ensure_ascii=False, indent=2)

    # Print summary
    meta = index.scan_metadata
    print(f"✅ Scan complete!")
    print(f"📊 Files scanned: {meta['files_scanned']}")
    print(f"⏱️  Duration: {meta['duration_seconds']}s")
    print(f"📝 Output: {output_path}")
    print(
        f"🔗 Git commit: {meta['git_commit'][:8] if meta['git_commit'] != 'unknown' else 'unknown'}"
    )


if __name__ == "__main__":
    main()
