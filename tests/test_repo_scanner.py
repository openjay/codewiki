"""
Tests for Code Wiki repository scanner.

PR #1: Basic functionality tests for scanner and orchestrator.
"""

import json
import time
from pathlib import Path

import pytest

from codewiki import repo_scanner


class TestRepoScanner:
    """Test suite for repository scanner."""

    @pytest.fixture
    def config_path(self):
        """Get path to config file."""
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "config" / "code_wiki_config.yaml"

    @pytest.fixture
    def config(self, config_path):
        """Load configuration."""
        return repo_scanner.load_code_wiki_config(config_path)

    def test_config_loading(self, config_path):
        """Test configuration file can be loaded."""
        config = repo_scanner.load_code_wiki_config(config_path)
        assert config is not None
        assert "scan_settings" in config
        assert "version" in config
        assert config["version"] == "1.0"

    def test_config_has_required_fields(self, config):
        """Test configuration has all required fields."""
        assert "scan_settings" in config
        assert "include_paths" in config["scan_settings"]
        assert "exclude_patterns" in config["scan_settings"]
        assert "output" in config
        assert "index_path" in config["output"]

    def test_scan_repository_returns_index(self, config):
        """Test that scan_repository returns a valid RepoIndex."""
        index = repo_scanner.scan_repository(config)

        assert index is not None
        assert hasattr(index, "scan_metadata")
        assert hasattr(index, "files")
        assert isinstance(index.files, list)

    def test_scan_metadata_structure(self, config):
        """Test scan metadata has required fields."""
        index = repo_scanner.scan_repository(config)
        meta = index.scan_metadata

        assert "project_root" in meta
        assert "timestamp" in meta
        assert "git_commit" in meta
        assert "duration_seconds" in meta
        assert "files_scanned" in meta
        assert "config_version" in meta

    def test_scan_finds_files(self, config):
        """Test that scan actually finds files."""
        index = repo_scanner.scan_repository(config)

        # Should find many files in this project
        assert len(index.files) > 100
        assert index.scan_metadata["files_scanned"] > 100

    def test_file_classification(self, config):
        """Test that files are classified correctly."""
        index = repo_scanner.scan_repository(config)

        # Collect file kinds
        kinds = {f.kind for f in index.files}

        # Should have multiple file kinds
        assert len(kinds) >= 3

        # Should have these specific kinds
        assert "python" in kinds
        assert "test" in kinds

    def test_python_files_have_language(self, config):
        """Test that Python files are marked with language."""
        index = repo_scanner.scan_repository(config)

        python_files = [f for f in index.files if f.kind == "python"]
        assert len(python_files) > 0

        # All Python files should have language set
        for f in python_files:
            assert f.language == "python"

    def test_test_files_are_marked(self, config):
        """Test that test files are correctly marked."""
        index = repo_scanner.scan_repository(config)

        test_files = [f for f in index.files if f.is_test]
        assert len(test_files) > 0

        # All test files should have kind="test"
        for f in test_files:
            assert f.kind == "test"

    def test_scan_performance(self, config):
        """Test that scan completes within performance target (<5s).

        Note: The 5s target is from CODE_WIKI_DESIGN.md and provides early
        warning for performance regressions. Current performance is ~0.018s
        for 661 files (277× margin), so failures indicate real issues.
        """
        start = time.time()
        index = repo_scanner.scan_repository(config)
        duration = time.time() - start

        # Should complete in less than 5 seconds (target: <5s from design doc)
        assert duration < 5.0, f"Scan took {duration:.3f}s, expected <5s"

        # Also check the reported duration
        assert index.scan_metadata["duration_seconds"] < 5.0

    def test_repo_index_to_dict(self, config):
        """Test conversion of RepoIndex to dictionary."""
        index = repo_scanner.scan_repository(config)
        index_dict = repo_scanner.repo_index_to_dict(index)

        assert isinstance(index_dict, dict)
        assert "scan_metadata" in index_dict
        assert "files" in index_dict
        assert isinstance(index_dict["files"], list)

        # Test that it's JSON serializable
        json_str = json.dumps(index_dict)
        assert len(json_str) > 0

    def test_exclude_patterns_work(self, config):
        """Test that exclude patterns filter out files."""
        index = repo_scanner.scan_repository(config)

        # Should not contain __pycache__ files
        pycache_files = [f for f in index.files if "__pycache__" in f.path]
        assert len(pycache_files) == 0

        # Should not contain .pyc files
        pyc_files = [f for f in index.files if f.path.endswith(".pyc")]
        assert len(pyc_files) == 0

    def test_git_commit_extraction(self):
        """Test git commit hash extraction."""
        commit_hash = repo_scanner._get_git_commit()

        # Should return a hash or 'unknown'
        assert commit_hash is not None
        assert len(commit_hash) > 0

        # In a git repo, should return a 40-char hash
        if commit_hash != "unknown":
            assert len(commit_hash) == 40
            # Should be hex
            int(commit_hash, 16)

    def test_file_metadata(self, config):
        """Test that file metadata is correctly extracted."""
        index = repo_scanner.scan_repository(config)

        # Pick first file
        if len(index.files) > 0:
            file_entry = index.files[0]

            assert file_entry.path is not None
            assert len(file_entry.path) > 0
            assert file_entry.size_bytes >= 0
            assert file_entry.mtime > 0
            assert file_entry.kind in {
                "python",
                "config",
                "test",
                "script",
                "doc",
                "other",
                "typescript",
                "javascript",
            }
