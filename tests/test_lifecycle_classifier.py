"""
Unit tests for lifecycle_classifier.py

Tests the file lifecycle classification logic including:
- Rule-based classification
- Age-based recommendations
- Pattern detection (archive, legacy, backup)
- Confidence scoring
- Result serialization
"""

import json
import time
from pathlib import Path

import pytest

from codewiki.lifecycle_classifier import (
    FileLifecycleRecommendation,
    LifecycleClassifier,
    run_lifecycle_classification,
)


@pytest.fixture
def sample_repo_index(tmp_path: Path) -> Path:
    """Create a sample repo_index.json for testing."""
    index_path = tmp_path / "repo_index.json"
    now = time.time()
    seconds_per_day = 86400

    payload = {
        "scan_metadata": {
            "timestamp": "2025-11-15T10:00:00Z",
            "git_commit": "abc123",
            "files_scanned": 6,
        },
        "files": [
            # Active file (recently modified)
            {
                "path": "digital_me/core/new_feature.py",
                "mtime": now - 10 * seconds_per_day,
                "size_bytes": 1000,
                "kind": "python",
            },
            # Old file (should review)
            {
                "path": "scripts/old_tool.py",
                "mtime": now - 120 * seconds_per_day,
                "size_bytes": 500,
                "kind": "script",
            },
            # Very old file (should archive)
            {
                "path": "legacy_code/ancient.py",
                "mtime": now - 300 * seconds_per_day,
                "size_bytes": 2000,
                "kind": "python",
            },
            # File with legacy pattern
            {
                "path": "utils/helper_legacy.py",
                "mtime": now - 50 * seconds_per_day,
                "size_bytes": 800,
                "kind": "python",
            },
            # Backup file (should delete)
            {
                "path": "config.py.bak",
                "mtime": now - 20 * seconds_per_day,
                "size_bytes": 200,
                "kind": "other",
            },
            # Already archived file
            {
                "path": "docs/archive/old_doc.md",
                "mtime": now - 200 * seconds_per_day,
                "size_bytes": 1500,
                "kind": "doc",
            },
        ],
    }

    index_path.write_text(json.dumps(payload), encoding="utf-8")
    return index_path


def test_lifecycle_classifier_loads_index(sample_repo_index: Path, tmp_path: Path):
    """Test that classifier can load repo index."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    index = classifier.load_repo_index()
    assert "scan_metadata" in index
    assert "files" in index
    assert len(index["files"]) == 6


def test_lifecycle_classifier_missing_index(tmp_path: Path):
    """Test error handling when index file doesn't exist."""
    missing_path = tmp_path / "nonexistent.json"
    output_path = tmp_path / "output.json"

    classifier = LifecycleClassifier(
        index_path=missing_path,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    with pytest.raises(FileNotFoundError):
        classifier.load_repo_index()


def test_lifecycle_classifier_creates_recommendations(
    sample_repo_index: Path, tmp_path: Path
):
    """Test that classifier generates recommendations for all files."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()
    assert len(result.recommendations) == 6
    assert result.scan_metadata["classification_method"] == "rule-based-v1"


def test_lifecycle_classifier_summary(sample_repo_index: Path, tmp_path: Path):
    """Test summary statistics generation."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()
    classifier.save_result(result)

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert "summary" in data
    summary = data["summary"]
    assert summary["total_files"] == 6
    assert "by_decision" in summary
    assert "confidence_distribution" in summary


def test_lifecycle_classifier_recommendation_types(
    sample_repo_index: Path, tmp_path: Path
):
    """Test that different recommendation types are generated correctly."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()

    # Group by recommendation type
    by_type = {}
    for rec in result.recommendations:
        by_type.setdefault(rec.recommendation, []).append(rec)

    # Should have multiple types
    assert len(by_type) >= 3

    # Should have "keep" recommendations (active files)
    assert "keep" in by_type
    assert any("new_feature.py" in r.path for r in by_type["keep"])

    # Should have "archive" recommendations (very old files or already archived)
    assert "archive" in by_type
    assert any("ancient.py" in r.path for r in by_type["archive"])
    assert any("archive/old_doc.md" in r.path for r in by_type["archive"])

    # Should have "delete" recommendations (backup files)
    assert "delete" in by_type
    assert any(".bak" in r.path for r in by_type["delete"])

    # Should have "review" recommendations (old files)
    assert "review" in by_type
    assert any("old_tool.py" in r.path for r in by_type["review"])


def test_lifecycle_classifier_pattern_detection(
    sample_repo_index: Path, tmp_path: Path
):
    """Test pattern-based classification (legacy, backup, archive)."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()

    # Find specific files
    legacy_file = next(
        r for r in result.recommendations if "helper_legacy.py" in r.path
    )
    backup_file = next(r for r in result.recommendations if ".bak" in r.path)
    archive_file = next(r for r in result.recommendations if "archive/" in r.path)

    # Legacy pattern should suggest archive
    assert legacy_file.recommendation == "archive"
    assert legacy_file.confidence >= 0.85

    # Backup pattern should suggest delete
    assert backup_file.recommendation == "delete"
    assert backup_file.confidence >= 0.85

    # Already archived should stay archive with high confidence
    assert archive_file.recommendation == "archive"
    assert archive_file.confidence >= 0.9


def test_lifecycle_classifier_confidence_scores(
    sample_repo_index: Path, tmp_path: Path
):
    """Test that confidence scores are within valid range."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()

    for rec in result.recommendations:
        # All confidence scores should be between 0 and 1
        assert 0.0 <= rec.confidence <= 1.0
        # All should have reasons
        assert len(rec.reasons) > 0


def test_lifecycle_classifier_age_thresholds(tmp_path: Path):
    """Test age-based classification with different deprecation thresholds."""
    # Create test index with known ages
    index_path = tmp_path / "repo_index.json"
    now = time.time()
    seconds_per_day = 86400

    payload = {
        "scan_metadata": {"timestamp": "2025-11-15T10:00:00Z"},
        "files": [
            {
                "path": "file_90days.py",
                "mtime": now - 90 * seconds_per_day,
                "kind": "python",
            },
            {
                "path": "file_135days.py",
                "mtime": now - 135 * seconds_per_day,
                "kind": "python",
            },
            {
                "path": "file_270days.py",
                "mtime": now - 270 * seconds_per_day,
                "kind": "python",
            },
            {
                "path": "file_30days.py",
                "mtime": now - 30 * seconds_per_day,
                "kind": "python",
            },
        ],
    }
    index_path.write_text(json.dumps(payload), encoding="utf-8")

    output_path = tmp_path / "output.json"
    classifier = LifecycleClassifier(
        index_path=index_path,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()

    # 30 days: should keep (recent)
    file_30 = next(r for r in result.recommendations if "file_30days.py" in r.path)
    assert file_30.recommendation == "keep"

    # 90 days: should review (exactly at threshold)
    file_90 = next(r for r in result.recommendations if "file_90days.py" in r.path)
    assert file_90.recommendation == "review"

    # 135 days: should review (1.5× threshold)
    file_135 = next(r for r in result.recommendations if "file_135days.py" in r.path)
    assert file_135.recommendation == "review"

    # 270 days: should archive (3× threshold)
    file_270 = next(r for r in result.recommendations if "file_270days.py" in r.path)
    assert file_270.recommendation == "archive"


def test_run_lifecycle_classification_dry_run(
    sample_repo_index: Path, tmp_path: Path, capsys
):
    """Test dry-run mode (preview without writing)."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    run_lifecycle_classification(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
        dry_run=True,
    )

    # File should not be created in dry-run
    assert not output_path.exists()

    # Should print preview to stdout
    captured = capsys.readouterr()
    assert "Lifecycle Classification Preview" in captured.out
    assert "Total files:" in captured.out
    assert "Would write to:" in captured.out


def test_run_lifecycle_classification_writes_file(
    sample_repo_index: Path, tmp_path: Path
):
    """Test that lifecycle classification writes output file."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    run_lifecycle_classification(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
        dry_run=False,
    )

    # File should be created
    assert output_path.exists()

    # Verify structure
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert "scan_metadata" in data
    assert "recommendations" in data
    assert "summary" in data
    assert len(data["recommendations"]) == 6


def test_lifecycle_classifier_suggested_actions(
    sample_repo_index: Path, tmp_path: Path
):
    """Test that suggested actions are generated for actionable items."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()

    # Archive recommendations should have suggested actions
    archive_recs = [r for r in result.recommendations if r.recommendation == "archive"]
    for rec in archive_recs:
        if "archive/" not in rec.path.lower():  # Not already archived
            assert rec.suggested_action is not None
            assert "Move to" in rec.suggested_action

    # Delete recommendations should have suggested actions
    delete_recs = [r for r in result.recommendations if r.recommendation == "delete"]
    for rec in delete_recs:
        assert rec.suggested_action is not None
        assert "Delete" in rec.suggested_action


def test_lifecycle_classifier_serialization_format(
    sample_repo_index: Path, tmp_path: Path
):
    """Test the JSON output format matches expected structure."""
    output_path = tmp_path / "lifecycle_recommendations.json"

    classifier = LifecycleClassifier(
        index_path=sample_repo_index,
        output_path=output_path,
        deprecation_days=90,
        confidence_threshold=0.7,
    )

    result = classifier.classify()
    classifier.save_result(result)

    data = json.loads(output_path.read_text(encoding="utf-8"))

    # Verify top-level structure
    assert set(data.keys()) == {"scan_metadata", "recommendations", "summary"}

    # Verify scan_metadata
    metadata = data["scan_metadata"]
    assert "source_index" in metadata
    assert "generated_at" in metadata
    assert "deprecation_days" in metadata
    assert "classification_method" in metadata

    # Verify recommendation structure
    for rec in data["recommendations"]:
        assert set(rec.keys()) == {
            "path",
            "recommendation",
            "confidence",
            "reasons",
            "suggested_action",
        }
        assert rec["recommendation"] in ["keep", "archive", "delete", "review"]
        assert isinstance(rec["confidence"], (int, float))
        assert isinstance(rec["reasons"], list)

    # Verify summary structure
    summary = data["summary"]
    assert "total_files" in summary
    assert "by_decision" in summary
    assert "confidence_distribution" in summary
    assert summary["total_files"] == 6
