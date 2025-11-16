# scripts/documentation/doc_generator.py
"""
Code Wiki Documentation Generator

Generates human-readable Markdown documentation from repository scan data:
- Architecture overview with statistics and diagrams
- Service/script catalog with lifecycle information
- Optional README.md controlled block updates

V1: Pure Python template-based generation (no LLM dependency)
Future: Can integrate LLM via digital_me/core/llm/factory.py for enhanced analysis
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RepoStats:
    """Repository statistics extracted from scan metadata."""

    total_files: int
    by_kind: Dict[str, int]
    latest_commit: Optional[str]
    generated_at: str


@dataclass
class ServiceEntry:
    """Represents a service or script in the catalog."""

    name: str
    path: str
    kind: str  # python, script, config, etc.
    lifecycle: str  # keep, archive, delete, review
    size_bytes: int


class CodeWikiDocGenerator:
    """
    Documentation generator for Code Wiki system.

    Converts structured JSON data (repo_index.json + lifecycle_recommendations.json)
    into human-readable Markdown documentation files.
    """

    def __init__(
        self,
        index_path: Path,
        lifecycle_path: Optional[Path],
        output_dir: Path,
        readme_path: Optional[Path] = None,
    ) -> None:
        """
        Initialize documentation generator.

        Args:
            index_path: Path to repo_index.json
            lifecycle_path: Path to lifecycle_recommendations.json (optional)
            output_dir: Directory to write generated docs
            readme_path: Path to README.md for controlled block updates (optional)
        """
        self.index_path = index_path
        self.lifecycle_path = lifecycle_path
        self.output_dir = output_dir
        self.readme_path = readme_path

        self._index: Dict[str, Any] = {}
        self._lifecycle: Dict[str, Any] = {}

    def load_inputs(self) -> None:
        """Load repository index and lifecycle recommendations from JSON files."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"Repository index not found: {self.index_path}")

        with self.index_path.open("r", encoding="utf-8") as f:
            self._index = json.load(f)

        if self.lifecycle_path and self.lifecycle_path.exists():
            with self.lifecycle_path.open("r", encoding="utf-8") as f:
                self._lifecycle = json.load(f)
        else:
            self._lifecycle = {"recommendations": []}

    def build_repo_stats(self) -> RepoStats:
        """
        Extract repository statistics from loaded index.

        Returns:
            RepoStats with file counts, classifications, and metadata
        """
        files = self._index.get("files", [])
        by_kind: Dict[str, int] = {}

        for entry in files:
            kind = entry.get("kind", "other")
            by_kind[kind] = by_kind.get(kind, 0) + 1

        scan_meta = self._index.get("scan_metadata", {})

        # Use actual scan timestamp from index, fallback to current time if not present
        scan_timestamp = scan_meta.get("timestamp")
        if not scan_timestamp:
            scan_timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        return RepoStats(
            total_files=len(files),
            by_kind=by_kind,
            latest_commit=scan_meta.get("git_commit"),
            generated_at=scan_timestamp,
        )

    def build_services(self) -> List[ServiceEntry]:
        """
        Build service catalog from index and lifecycle data.

        Returns:
            List of ServiceEntry objects for all Python files and scripts
        """
        files = self._index.get("files", [])

        # Build lifecycle lookup map
        lifecycle_map = {
            rec["path"]: rec["recommendation"]
            for rec in self._lifecycle.get("recommendations", [])
        }

        services: List[ServiceEntry] = []

        for entry in files:
            path = entry["path"]
            kind = entry.get("kind", "other")

            # V1: Only include Python files and scripts in service catalog
            # Future: Can expand to include APIs, agents, services based on annotations
            if kind not in {"python", "script"}:
                continue

            services.append(
                ServiceEntry(
                    name=Path(path).stem,
                    path=path,
                    kind=kind,
                    lifecycle=lifecycle_map.get(path, "keep"),
                    size_bytes=entry.get("size_bytes", 0),
                )
            )

        return services

    def generate_overview_markdown(
        self, stats: RepoStats, services: List[ServiceEntry]
    ) -> str:
        """
        Generate architecture overview document.

        V1: Template-based generation with basic stats and Mermaid diagram
        Future: Can integrate LLM for enhanced analysis and insights

        Args:
            stats: Repository statistics
            services: List of services for high-level summary

        Returns:
            Markdown document as string
        """
        header = textwrap.dedent(
            f"""\
            <!--
            AUTO-GENERATED by Code Wiki System
            Generated: {stats.generated_at}
            Source: {self.index_path}
            Commit: {stats.latest_commit or 'unknown'}
            DO NOT EDIT MANUALLY
            Regenerate using: make code-wiki-docgen
            -->

            # Code Wiki – Architecture Overview

            This document is auto-generated by the Code Wiki system to provide an overview
            of the current codebase structure and statistics.
            """
        )

        # Statistics section
        stats_block = "## Repository Statistics\n\n"
        stats_block += f"- **Total files**: {stats.total_files}\n"
        stats_block += f"- **Last scan**: {stats.generated_at}\n"
        stats_block += f"- **Git commit**: `{stats.latest_commit or 'unknown'}`\n\n"

        stats_block += "### File Breakdown\n\n"
        for kind in sorted(stats.by_kind.keys()):
            count = stats.by_kind[kind]
            percentage = (
                (count / stats.total_files * 100) if stats.total_files > 0 else 0
            )
            stats_block += f"- **{kind}**: {count} files ({percentage:.1f}%)\n"

        # High-level architecture diagram
        mermaid_section = textwrap.dedent(
            """\
            ## System Architecture

            The Code Wiki system consists of three main phases:

            ```mermaid
            graph LR
              A[Codebase] --> B[Repo Scanner]
              B --> C[repo_index.json]
              C --> D[Lifecycle Classifier]
              D --> E[lifecycle_recommendations.json]
              C --> F[Doc Generator]
              E --> F
              F --> G[*.generated.md]
              F --> H[README.md blocks]
            ```

            ### Components

            1. **Repo Scanner**: Traverses file system, classifies files, extracts metadata
            2. **Lifecycle Classifier**: Analyzes file age and patterns, recommends actions
            3. **Doc Generator**: Converts structured data to human-readable documentation
            """
        )

        # Service summary
        service_summary = f"\n## Service Catalog Summary\n\n"
        service_summary += f"Total services/scripts indexed: **{len(services)}**\n\n"

        if services:
            by_lifecycle = {}
            for s in services:
                by_lifecycle[s.lifecycle] = by_lifecycle.get(s.lifecycle, 0) + 1

            service_summary += "Lifecycle distribution:\n"
            for lifecycle in sorted(by_lifecycle.keys()):
                count = by_lifecycle[lifecycle]
                service_summary += f"- **{lifecycle}**: {count} files\n"

            service_summary += f"\nFor detailed service catalog, see [SERVICE_CATALOG.generated.md](SERVICE_CATALOG.generated.md)\n"

        return "\n".join([header, stats_block, mermaid_section, service_summary])

    def generate_service_catalog_markdown(self, services: List[ServiceEntry]) -> str:
        """
        Generate service catalog document with table of all services.

        Args:
            services: List of services to include

        Returns:
            Markdown document as string
        """
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        header = textwrap.dedent(
            f"""\
            <!--
            AUTO-GENERATED by Code Wiki System
            Generated: {now}
            Source: {self.index_path}
            DO NOT EDIT MANUALLY
            Regenerate using: make code-wiki-docgen
            -->

            # Code Wiki – Service & Script Catalog

            This catalog lists all Python files and scripts discovered in the repository,
            along with their lifecycle status and basic metadata.
            """
        )

        if not services:
            return header + "\n\n*No services or scripts found.*\n"

        # Build table
        table_lines = [
            "| Name | Path | Kind | Lifecycle | Size |",
            "|------|------|------|-----------|------|",
        ]

        for s in sorted(services, key=lambda x: x.path):
            size_kb = s.size_bytes / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{s.size_bytes} B"

            # Emoji indicators for lifecycle
            lifecycle_emoji = {
                "keep": "✅",
                "archive": "📦",
                "delete": "🗑️",
                "review": "⚠️",
            }
            lifecycle_display = f"{lifecycle_emoji.get(s.lifecycle, '❓')} {s.lifecycle}"

            table_lines.append(
                f"| `{s.name}` | `{s.path}` | {s.kind} | {lifecycle_display} | {size_str} |"
            )

        legend = textwrap.dedent(
            """
            ## Lifecycle Legend

            - ✅ **keep**: Active file, in regular use
            - ⚠️ **review**: Potentially deprecated, needs human review
            - 📦 **archive**: Should be moved to archive directory
            - 🗑️ **delete**: Backup/temporary file, safe to remove
            """
        )

        return "\n\n".join([header, "\n".join(table_lines), legend])

    def update_readme_sections(self, stats: RepoStats, preview: bool = False) -> None:
        """
        Update controlled sections in README.md.

        Uses <!-- CODE_WIKI_START:section_name --> / <!-- CODE_WIKI_END:section_name -->
        markers to identify and replace sections.

        Args:
            stats: Repository statistics for summary generation
            preview: If True, only print what would be changed (no writes)
        """
        if not self.readme_path or not self.readme_path.exists():
            return

        raw = self.readme_path.read_text(encoding="utf-8")

        def replace_block(content: str, block_name: str, new_content: str) -> str:
            """Replace content between CODE_WIKI_START/END markers."""
            start_marker = f"<!-- CODE_WIKI_START:{block_name} -->"
            end_marker = f"<!-- CODE_WIKI_END:{block_name} -->"

            if start_marker not in content or end_marker not in content:
                # Block not found, skip
                return content

            before, rest = content.split(start_marker, 1)
            _, after = rest.split(end_marker, 1)

            return (
                before + start_marker + "\n" + new_content + "\n" + end_marker + after
            )

        # Generate quick stats summary for README
        summary_lines = [
            f"**Repository Statistics** (auto-updated by Code Wiki)",
            f"- Total files: {stats.total_files}",
            f"- Last scan: {stats.generated_at}",
        ]

        # Top 3 file types
        sorted_kinds = sorted(stats.by_kind.items(), key=lambda x: x[1], reverse=True)[
            :3
        ]
        if sorted_kinds:
            summary_lines.append(
                "- Top file types: " + ", ".join(f"{k} ({c})" for k, c in sorted_kinds)
            )

        summary = "\n".join(summary_lines)

        # Apply replacement
        updated = replace_block(raw, "quick_stats", summary)

        if preview:
            print(
                f"\n[Preview] Would update README.md block 'quick_stats' with:\n{summary}\n"
            )
            return

        if updated != raw:
            self.readme_path.write_text(updated, encoding="utf-8")
            print(f"✅ Updated README.md controlled section: quick_stats")
        else:
            print(f"ℹ️  README.md block 'quick_stats' not found (markers not present)")

    def write_file(
        self, relative_path: str, content: str, preview: bool = False
    ) -> None:
        """
        Write generated documentation to file.

        Args:
            relative_path: Path relative to output_dir
            content: Markdown content to write
            preview: If True, only print summary (no writes)
        """
        target = self.output_dir / relative_path

        if preview:
            line_count = len(content.split("\n"))
            char_count = len(content)
            print(
                f"\n[Preview] Would write to {target}:\n"
                f"  - Lines: {line_count}\n"
                f"  - Characters: {char_count}\n"
            )
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"✅ Generated: {target}")


def run_doc_generation(
    index_path: Path,
    lifecycle_path: Optional[Path],
    output_dir: Path,
    readme_path: Optional[Path],
    preview: bool = False,
) -> None:
    """
    Main entry point for documentation generation.

    Args:
        index_path: Path to repo_index.json
        lifecycle_path: Path to lifecycle_recommendations.json (optional)
        output_dir: Directory to write generated docs
        readme_path: Path to README.md (optional)
        preview: If True, show what would be generated without writing
    """
    print(f"📝 [code-wiki] Generating documentation from {index_path}...")

    generator = CodeWikiDocGenerator(
        index_path=index_path,
        lifecycle_path=lifecycle_path,
        output_dir=output_dir,
        readme_path=readme_path,
    )

    # Load input data
    generator.load_inputs()

    # Build data structures
    stats = generator.build_repo_stats()
    services = generator.build_services()

    # Generate documentation
    overview = generator.generate_overview_markdown(stats, services)
    catalog = generator.generate_service_catalog_markdown(services)

    # Write output files
    generator.write_file("CODE_WIKI_OVERVIEW.generated.md", overview, preview=preview)
    generator.write_file("SERVICE_CATALOG.generated.md", catalog, preview=preview)

    # Update README if enabled
    if readme_path:
        generator.update_readme_sections(stats, preview=preview)

    if preview:
        print("\n🔍 [code-wiki] Preview mode: No files were written")
    else:
        print(f"\n✅ [code-wiki] Documentation generation complete!")
        print(f"   Output directory: {output_dir}")
        print(f"   Files generated: 2")
