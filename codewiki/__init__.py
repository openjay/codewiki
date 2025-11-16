"""
CodeWiki - LLM-enhanced code lifecycle analysis and documentation generator.

A standalone tool for:
- Repository scanning and metadata extraction
- File lifecycle classification (keep/review/archive/delete)
- Automated documentation generation
- LLM-powered code analysis (Ollama + LM Studio)

Version: 1.2.0
"""

__version__ = "1.2.0"
__author__ = "Jay"
__description__ = "LLM-enhanced code lifecycle analysis and documentation generator"

from .doc_generator import CodeWikiDocGenerator, run_doc_generation
from .lifecycle_classifier import (
    FileLifecycleRecommendation,
    LifecycleClassifier,
    LifecycleResult,
    run_lifecycle_classification,
)

# Public API exports (use relative imports)
from .repo_scanner import FileEntry, RepoIndex, repo_index_to_dict, scan_repository

# LLM client is optional (requires requests library)
try:
    from .llm_client import LocalLLMClient, ProviderConfig

    HAS_LLM = True
except ImportError:
    LocalLLMClient = None
    ProviderConfig = None
    HAS_LLM = False

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "FileEntry",
    "RepoIndex",
    "scan_repository",
    "repo_index_to_dict",
    "LifecycleClassifier",
    "FileLifecycleRecommendation",
    "LifecycleResult",
    "run_lifecycle_classification",
    "CodeWikiDocGenerator",
    "run_doc_generation",
    "LocalLLMClient",
    "ProviderConfig",
]
