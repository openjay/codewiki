# tests/documentation/test_doc_generator.py

import json
import time
from pathlib import Path

import pytest

from codewiki.doc_generator import (
    CodeWikiDocGenerator,
    RepoStats,
    ServiceEntry,
    run_doc_generation,
)


@pytest.fixture
def mock_repo_index(tmp_path: Path) -> Path:
    """Creates a mock repo_index.json for testing."""
    index_path = tmp_path / "repo_index.json"
    now = time.time()
    seconds_per_day = 86400

    payload = {
        "scan_metadata": {
            "timestamp": "2025-11-15T20:00:00Z",
            "git_commit": "abc1234567890",
            "files_scanned": 10,
            "duration_seconds": 0.02,
        },
        "files": [
            # Python files
            {
                "path": "digital_me/core/main.py",
                "kind": "python",
                "size_bytes": 1024,
                "mtime": now - 10 * seconds_per_day,
            },
            {
                "path": "digital_me/agents/test_agent.py",
                "kind": "python",
                "size_bytes": 2048,
                "mtime": now - 20 * seconds_per_day,
            },
            {
                "path": "scripts/helper.py",
                "kind": "script",
                "size_bytes": 512,
                "mtime": now - 5 * seconds_per_day,
            },
            # Config files (should not appear in service catalog)
            {
                "path": "config/settings.yaml",
                "kind": "config",
                "size_bytes": 256,
                "mtime": now - 15 * seconds_per_day,
            },
            {
                "path": "requirements.txt",
                "kind": "config",
                "size_bytes": 128,
                "mtime": now - 30 * seconds_per_day,
            },
            # Test files
            {
                "path": "tests/test_core.py",
                "kind": "test",
                "size_bytes": 3072,
                "mtime": now - 7 * seconds_per_day,
            },
            # Doc files
            {
                "path": "docs/README.md",
                "kind": "doc",
                "size_bytes": 2048,
                "mtime": now - 25 * seconds_per_day,
            },
            # More Python
            {
                "path": "digital_me/utils/helpers.py",
                "kind": "python",
                "size_bytes": 768,
                "mtime": now - 12 * seconds_per_day,
            },
            {
                "path": "scripts/deploy.sh",
                "kind": "script",
                "size_bytes": 640,
                "mtime": now - 8 * seconds_per_day,
            },
            # Other
            {
                "path": "LICENSE",
                "kind": "other",
                "size_bytes": 1024,
                "mtime": now - 365 * seconds_per_day,
            },
        ],
    }
    index_path.write_text(json.dumps(payload), encoding="utf-8")
    return index_path


@pytest.fixture
def mock_lifecycle_recommendations(tmp_path: Path) -> Path:
    """Creates a mock lifecycle_recommendations.json for testing."""
    lifecycle_path = tmp_path / "lifecycle_recommendations.json"
    payload = {
        "scan_metadata": {"timestamp": "2025-11-15T20:00:00Z"},
        "recommendations": [
            {"path": "digital_me/core/main.py", "recommendation": "keep"},
            {"path": "digital_me/agents/test_agent.py", "recommendation": "keep"},
            {"path": "scripts/helper.py", "recommendation": "keep"},
            {"path": "digital_me/utils/helpers.py", "recommendation": "review"},
            {"path": "scripts/deploy.sh", "recommendation": "archive"},
        ],
    }
    lifecycle_path.write_text(json.dumps(payload), encoding="utf-8")
    return lifecycle_path


@pytest.fixture
def doc_generator(
    mock_repo_index: Path,
    mock_lifecycle_recommendations: Path,
    tmp_path: Path,
) -> CodeWikiDocGenerator:
    """Creates a configured CodeWikiDocGenerator instance."""
    generator = CodeWikiDocGenerator(
        index_path=mock_repo_index,
        lifecycle_path=mock_lifecycle_recommendations,
        output_dir=tmp_path / "output",
        readme_path=None,
    )
    generator.load_inputs()
    return generator


def test_load_inputs_success(doc_generator: CodeWikiDocGenerator) -> None:
    """Test that inputs are loaded successfully."""
    assert doc_generator._index is not None
    assert doc_generator._lifecycle is not None
    assert "files" in doc_generator._index
    assert "recommendations" in doc_generator._lifecycle


def test_load_inputs_missing_index(tmp_path: Path) -> None:
    """Test that missing index file raises FileNotFoundError."""
    generator = CodeWikiDocGenerator(
        index_path=tmp_path / "nonexistent.json",
        lifecycle_path=None,
        output_dir=tmp_path,
    )
    with pytest.raises(FileNotFoundError):
        generator.load_inputs()


def test_load_inputs_missing_lifecycle(mock_repo_index: Path, tmp_path: Path) -> None:
    """Test that missing lifecycle file is handled gracefully."""
    generator = CodeWikiDocGenerator(
        index_path=mock_repo_index,
        lifecycle_path=tmp_path / "nonexistent.json",  # File doesn't exist
        output_dir=tmp_path,
    )
    generator.load_inputs()  # Should not raise
    assert generator._lifecycle == {"recommendations": []}


def test_build_repo_stats(doc_generator: CodeWikiDocGenerator) -> None:
    """Test that repository statistics are built correctly."""
    stats = doc_generator.build_repo_stats()

    assert isinstance(stats, RepoStats)
    assert stats.total_files == 10
    assert stats.by_kind["python"] == 3
    assert stats.by_kind["config"] == 2
    assert stats.by_kind["test"] == 1
    assert stats.by_kind["doc"] == 1
    assert stats.by_kind["script"] == 2
    assert stats.by_kind["other"] == 1
    assert stats.latest_commit == "abc1234567890"
    assert stats.generated_at.endswith("Z")  # ISO format


def test_build_services(doc_generator: CodeWikiDocGenerator) -> None:
    """Test that service catalog is built correctly."""
    services = doc_generator.build_services()

    assert len(services) == 5  # 3 python + 2 scripts
    assert all(isinstance(s, ServiceEntry) for s in services)

    # Check that only python and script files are included
    kinds = {s.kind for s in services}
    assert kinds == {"python", "script"}

    # Check that lifecycles are correctly joined
    helper_service = next(s for s in services if "helper" in s.path)
    assert helper_service.lifecycle == "keep"

    deploy_service = next(s for s in services if "deploy" in s.path)
    assert deploy_service.lifecycle == "archive"

    helpers_service = next(s for s in services if "helpers" in s.path)
    assert helpers_service.lifecycle == "review"


def test_build_services_without_lifecycle(
    mock_repo_index: Path, tmp_path: Path
) -> None:
    """Test service catalog when lifecycle data is not available."""
    generator = CodeWikiDocGenerator(
        index_path=mock_repo_index,
        lifecycle_path=None,
        output_dir=tmp_path,
    )
    generator.load_inputs()
    services = generator.build_services()

    # All services should have "keep" as default lifecycle
    assert all(s.lifecycle == "keep" for s in services)


def test_generate_overview_markdown(doc_generator: CodeWikiDocGenerator) -> None:
    """Test that overview markdown is generated correctly."""
    stats = doc_generator.build_repo_stats()
    services = doc_generator.build_services()

    markdown = doc_generator.generate_overview_markdown(stats, services)

    # Check for required sections
    assert "AUTO-GENERATED by Code Wiki System" in markdown
    assert "# Code Wiki – Architecture Overview" in markdown
    assert "## Repository Statistics" in markdown
    assert "**Total files**: 10" in markdown
    assert "abc1234567890" in markdown  # Git commit

    # Check for file breakdown
    assert "**python**: 3 files" in markdown
    assert "**config**: 2 files" in markdown

    # Check for Mermaid diagram
    assert "```mermaid" in markdown
    assert "graph LR" in markdown
    assert "Repo Scanner" in markdown

    # Check for service summary
    assert "## Service Catalog Summary" in markdown
    assert "Total services/scripts indexed: **5**" in markdown


def test_generate_service_catalog_markdown(
    doc_generator: CodeWikiDocGenerator,
) -> None:
    """Test that service catalog markdown is generated correctly."""
    services = doc_generator.build_services()

    markdown = doc_generator.generate_service_catalog_markdown(services)

    # Check for header
    assert "AUTO-GENERATED by Code Wiki System" in markdown
    assert "# Code Wiki – Service & Script Catalog" in markdown
    assert "DO NOT EDIT MANUALLY" in markdown

    # Check for table structure
    assert "| Name | Path | Kind | Lifecycle | Size |" in markdown
    assert "|------|------|------|-----------|------|" in markdown

    # Check for specific entries
    assert "`main`" in markdown
    assert "`digital_me/core/main.py`" in markdown
    assert "python" in markdown

    # Check for lifecycle indicators
    assert "✅ keep" in markdown
    assert "⚠️ review" in markdown
    assert "📦 archive" in markdown

    # Check for legend
    assert "## Lifecycle Legend" in markdown


def test_generate_service_catalog_empty(tmp_path: Path) -> None:
    """Test service catalog generation when no services exist."""
    # Create index with only config files
    index_path = tmp_path / "index.json"
    payload = {
        "scan_metadata": {"timestamp": "2025-11-15T20:00:00Z", "git_commit": "abc123"},
        "files": [
            {"path": "config/settings.yaml", "kind": "config", "size_bytes": 256}
        ],
    }
    index_path.write_text(json.dumps(payload), encoding="utf-8")

    generator = CodeWikiDocGenerator(
        index_path=index_path, lifecycle_path=None, output_dir=tmp_path
    )
    generator.load_inputs()
    services = generator.build_services()

    markdown = generator.generate_service_catalog_markdown(services)

    assert "*No services or scripts found.*" in markdown


def test_update_readme_sections(
    tmp_path: Path, doc_generator: CodeWikiDocGenerator
) -> None:
    """Test that README sections are updated correctly."""
    readme_path = tmp_path / "README.md"
    initial_content = """# Test Project

Some intro text.

<!-- CODE_WIKI_START:quick_stats -->
Old stats here
<!-- CODE_WIKI_END:quick_stats -->

More text.
"""
    readme_path.write_text(initial_content, encoding="utf-8")

    # Update generator with README path
    doc_generator.readme_path = readme_path

    stats = doc_generator.build_repo_stats()
    doc_generator.update_readme_sections(stats, preview=False)

    updated = readme_path.read_text(encoding="utf-8")

    # Check that block was updated
    assert "**Repository Statistics**" in updated
    assert "Total files: 10" in updated
    assert "Old stats here" not in updated

    # Check that markers are preserved
    assert "<!-- CODE_WIKI_START:quick_stats -->" in updated
    assert "<!-- CODE_WIKI_END:quick_stats -->" in updated


def test_update_readme_missing_markers(
    tmp_path: Path, doc_generator: CodeWikiDocGenerator
) -> None:
    """Test that README update is skipped when markers are missing."""
    readme_path = tmp_path / "README.md"
    initial_content = "# Test Project\n\nNo markers here.\n"
    readme_path.write_text(initial_content, encoding="utf-8")

    doc_generator.readme_path = readme_path

    stats = doc_generator.build_repo_stats()
    doc_generator.update_readme_sections(stats, preview=False)

    # Content should remain unchanged
    assert readme_path.read_text(encoding="utf-8") == initial_content


def test_update_readme_preview_mode(
    tmp_path: Path, doc_generator: CodeWikiDocGenerator, capsys
) -> None:
    """Test that README update in preview mode doesn't write files."""
    readme_path = tmp_path / "README.md"
    initial_content = """# Test
<!-- CODE_WIKI_START:quick_stats -->
Old
<!-- CODE_WIKI_END:quick_stats -->
"""
    readme_path.write_text(initial_content, encoding="utf-8")

    doc_generator.readme_path = readme_path

    stats = doc_generator.build_repo_stats()
    doc_generator.update_readme_sections(stats, preview=True)

    # File should not be modified
    assert readme_path.read_text(encoding="utf-8") == initial_content

    # But preview message should be printed
    captured = capsys.readouterr()
    assert "[Preview]" in captured.out


def test_write_file(doc_generator: CodeWikiDocGenerator, tmp_path: Path) -> None:
    """Test that files are written correctly."""
    content = "# Test Document\n\nSome content."
    doc_generator.output_dir = tmp_path

    doc_generator.write_file("test.md", content, preview=False)

    output_file = tmp_path / "test.md"
    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == content


def test_write_file_preview_mode(
    doc_generator: CodeWikiDocGenerator, tmp_path: Path, capsys
) -> None:
    """Test that write_file in preview mode doesn't create files."""
    content = "# Test Document"
    doc_generator.output_dir = tmp_path

    doc_generator.write_file("test.md", content, preview=True)

    # File should not exist
    output_file = tmp_path / "test.md"
    assert not output_file.exists()

    # Preview message should be printed
    captured = capsys.readouterr()
    assert "[Preview]" in captured.out
    assert "test.md" in captured.out


def test_run_doc_generation_end_to_end(
    mock_repo_index: Path, mock_lifecycle_recommendations: Path, tmp_path: Path
) -> None:
    """Test complete documentation generation workflow."""
    output_dir = tmp_path / "output"

    run_doc_generation(
        index_path=mock_repo_index,
        lifecycle_path=mock_lifecycle_recommendations,
        output_dir=output_dir,
        readme_path=None,
        preview=False,
    )

    # Check that output files were created
    overview_file = output_dir / "CODE_WIKI_OVERVIEW.generated.md"
    catalog_file = output_dir / "SERVICE_CATALOG.generated.md"

    assert overview_file.exists()
    assert catalog_file.exists()

    # Check content
    overview_content = overview_file.read_text(encoding="utf-8")
    assert "# Code Wiki – Architecture Overview" in overview_content

    catalog_content = catalog_file.read_text(encoding="utf-8")
    assert "# Code Wiki – Service & Script Catalog" in catalog_content


def test_run_doc_generation_preview_mode(
    mock_repo_index: Path, tmp_path: Path, capsys
) -> None:
    """Test documentation generation in preview mode."""
    output_dir = tmp_path / "output"

    run_doc_generation(
        index_path=mock_repo_index,
        lifecycle_path=None,
        output_dir=output_dir,
        readme_path=None,
        preview=True,
    )

    # No files should be created
    assert not (output_dir / "CODE_WIKI_OVERVIEW.generated.md").exists()
    assert not (output_dir / "SERVICE_CATALOG.generated.md").exists()

    # Preview messages should be printed
    captured = capsys.readouterr()
    assert "Preview mode" in captured.out
