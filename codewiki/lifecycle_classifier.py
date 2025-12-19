"""
File Lifecycle Classifier for Code Wiki System.

Analyzes repository files to classify them by lifecycle stage:
- keep: Active files in use
- archive: Old files that should be preserved but moved to archives
- delete: Deprecated files safe to remove
- review: Files requiring human review

V1 Implementation:
- Uses rule-based classification (modification time, file patterns)

V1.1 Enhancement:
- Optional LLM-based classification using local Ollama/LM Studio

V1.2 Hybrid Mode:
- Intelligent clear-case detection to reduce LLM calls
- Enhanced JSON parsing with multiple fallback strategies
- Conservative prompting for better structured output
- Configurable hybrid mode (full vs selective LLM usage)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

# Import LLM client (V1.1+)
# V2.0: Prefer LIR client for better performance
try:
    from .llm_client_lir import LIRLocalLLMClient, HAS_LIR
    HAS_LIR_CLIENT = HAS_LIR
except ImportError:
    HAS_LIR_CLIENT = False

try:
    from .llm_client import LocalLLMClient
    HAS_LLM_CLIENT = True
except ImportError:
    HAS_LLM_CLIENT = False

if not HAS_LIR_CLIENT and not HAS_LLM_CLIENT:
    logger.warning("No LLM client available, falling back to rule-based only")

LifecycleDecision = Literal["keep", "archive", "delete", "review"]


@dataclass
class FileLifecycleRecommendation:
    """Single file lifecycle recommendation."""

    path: str
    recommendation: LifecycleDecision
    confidence: float
    reasons: List[str]
    suggested_action: str | None = None


@dataclass
class LifecycleResult:
    """Complete lifecycle classification result."""

    scan_metadata: Dict[str, Any]
    recommendations: List[FileLifecycleRecommendation]


class LifecycleClassifier:
    """
    Classifies files by lifecycle stage.

    Current implementation uses rule-based logic:
    - File age (modification time)
    - File type patterns
    - Known archive/legacy patterns

    Future: Will integrate with digital_me/core/llm/factory.py for LLM-based
    classification using local Ollama/LM Studio models.
    """

    def __init__(
        self,
        index_path: Path,
        output_path: Path,
        deprecation_days: int = 90,
        confidence_threshold: float = 0.7,
        llm_mode: str = "full",  # NEW V1.2: "full" | "hybrid"
        llm_max_files: Optional[int] = None,  # NEW V1.2: max LLM calls in hybrid
    ) -> None:
        """
        Initialize lifecycle classifier.

        Args:
            index_path: Path to repo_index.json from scanner
            output_path: Where to write lifecycle_recommendations.json
            deprecation_days: Files older than this are candidates for review
            confidence_threshold: Minimum confidence for recommendations
            llm_mode: "full" (try LLM for all files) or "hybrid" (selective)
            llm_max_files: Maximum LLM calls in hybrid mode (None = no limit)
        """
        self.index_path = index_path
        self.output_path = output_path
        self.deprecation_days = deprecation_days
        self.confidence_threshold = confidence_threshold
        self.llm_mode = llm_mode
        self.llm_max_files = llm_max_files

        # V1.2: LLM statistics tracking
        self._llm_stats = {
            "attempts": 0,
            "successes": 0,
            "fallbacks": 0,
        }
        self._llm_parse_stats = {
            "attempts": 0,
            "parse_success": 0,
            "parse_failed": 0,
        }

    def load_repo_index(self) -> Dict[str, Any]:
        """Load repository index from scanner output."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"Repo index not found: {self.index_path}")
        with self.index_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # ==================== V1.2: JSON Parser Enhancement ====================

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove ```json ... ``` or ``` wrappers, return inner content."""
        text = text.strip()
        if "```" in text:
            if "```json" in text:
                parts = text.split("```json", 1)
                if len(parts) > 1 and "```" in parts[1]:
                    return parts[1].split("```", 1)[0].strip()
            parts = text.split("```")
            if len(parts) >= 3:
                return parts[1].strip()
        return text

    @classmethod
    def _parse_llm_json(cls, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to extract JSON from LLM output with multiple strategies.

        Strategy chain:
        1. Direct json.loads
        2. Strip code fences, then loads
        3. Find first '{' and last '}', extract and parse

        Returns:
            Parsed JSON dict or None on failure (triggers rule-based fallback)
        """
        cls_text = raw_text.strip()
        if not cls_text:
            return None

        # 1) Direct attempt
        try:
            return json.loads(cls_text)
        except Exception:
            pass

        # 2) Strip code fences
        stripped = cls._strip_code_fences(cls_text)
        try:
            return json.loads(stripped)
        except Exception:
            pass

        # 3) Extract first {...} block
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = stripped[first : last + 1]
            try:
                return json.loads(candidate)
            except Exception:
                logger.debug("Final JSON parse attempt failed")

        return None

    # ==================== V1.2: Age Calculation Helper ====================

    def _compute_age_days(self, mtime: float) -> float:
        """Calculate file age in days from modification timestamp."""
        now = time.time()
        return (now - mtime) / 86400.0

    # ==================== V1.2: Clear-Case Detection ====================

    def _is_clear_case(self, entry: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Determine if file is an obvious case that doesn't need LLM (V1.2 hybrid mode).

        Uses moderate threshold heuristics:
        - Recently modified core files → keep
        - Temp/backup/log files → archive
        - Very old docs → review

        Returns:
            (is_clear, forced_decision or None)
            - is_clear=True, forced_decision!=None → use this decision
            - is_clear=False → needs LLM or rule-based analysis
        """
        path = entry.get("path", "")
        kind = entry.get("kind", "other")
        mtime = entry.get("mtime", 0)
        age_days = self._compute_age_days(mtime)

        # 1) Obvious keep: recently modified core files
        core_dirs = (
            "digital_me/core",
            "digital_me/api",
            "digital_me/orchestration",
            "digital_me_platform",
            "scripts/",
            "tests/",
        )
        if age_days < 30 and any(path.startswith(d) for d in core_dirs):
            return True, "keep"

        # 2) Obvious archive: temp/backup/log files
        lower = path.lower()
        if any(s in lower for s in (".log", ".tmp", ".bak", "~", ".swp")):
            return True, "archive"

        # 3) Old docs: review (not auto-delete)
        if age_days > 365 and kind in ("md", "txt", "doc", "json"):
            return True, "review"

        # Uncertain: needs LLM or rule-based
        return False, None

    # ==================== V1.2: LLM Classification ====================

    def _classify_with_llm(
        self,
        entry: Dict[str, Any],
        llm_client: "LocalLLMClient",
    ) -> Optional[FileLifecycleRecommendation]:
        """
        Use local LLM to classify file lifecycle (V1.1+ with V1.2 enhancements).

        V1.2 improvements:
        - Enhanced JSON parsing with fallback strategies
        - Conservative prompting with strict JSON-only output
        - Low-confidence safety check (archive/delete → review)

        Args:
            entry: File entry from repo_index.json
            llm_client: LocalLLMClient instance

        Returns:
            FileLifecycleRecommendation if LLM succeeds, None to fallback to rules
        """
        path = entry.get("path", "")
        kind = entry.get("kind", "other")
        size = entry.get("size_bytes", 0)
        mtime = entry.get("mtime", 0)
        age_days = self._compute_age_days(mtime)

        # Build enhanced prompts (V1.2)
        system_prompt = (
            "You are a senior software engineer specializing in repository hygiene "
            "and lifecycle management. Your task is to classify files in a large codebase.\n\n"
            "STRICT OUTPUT RULES:\n"
            "1. You MUST output EXACTLY ONE JSON object.\n"
            "2. Do NOT include markdown, explanations, comments, or multiple JSON blocks.\n"
            "3. The JSON keys MUST be exactly: "
            '"recommendation", "confidence", "reasons", "suggested_action".\n'
            '4. \'recommendation\' MUST be one of: "keep", "review", "archive", "delete".\n'
            "5. 'confidence' MUST be a float between 0.0 and 1.0.\n"
            "6. 'reasons' MUST be a short list of human-readable strings.\n"
            "7. If you are uncertain, prefer 'review' with a medium confidence.\n"
        )

        user_prompt = f"""
Analyze the following file and decide its lifecycle status in the repository.

File information:
- Path: {path}
- Kind: {kind}
- Size: {size} bytes
- Age: {int(age_days)} days since last modification
- Deprecation threshold: {self.deprecation_days} days

Decision labels:
1. "keep"   - Active and should remain in place.
2. "review" - Potentially deprecated or unclear; needs human review.
3. "archive"- Historical or rarely used; move to archive but do not delete.
4. "delete" - Temporary, backup, or clearly obsolete; safe to remove.

Important considerations:
- Be conservative. When in doubt between 'delete' and 'review', choose 'review'.
- For very old files beyond the deprecation threshold, 'review' or 'archive' are preferred.
- For recently modified core code files, 'keep' is usually correct.

Respond with EXACTLY ONE JSON object, and NOTHING ELSE.
"""

        # Call LLM
        try:
            response_text = llm_client.generate(
                prompt=user_prompt.strip(),
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.warning("LLM call failed for %s: %s", path, e)
            self._llm_stats["fallbacks"] += 1
            return None

        if not response_text:
            logger.debug("Empty LLM response for %s", path)
            self._llm_stats["fallbacks"] += 1
            return None

        # Parse JSON with enhanced parser (V1.2)
        self._llm_parse_stats["attempts"] += 1
        parsed = self._parse_llm_json(response_text)

        if not parsed:
            self._llm_parse_stats["parse_failed"] += 1
            self._llm_stats["fallbacks"] += 1
            logger.debug("LLM JSON parse failed for %s", path)
            return None

        self._llm_parse_stats["parse_success"] += 1
        self._llm_stats["successes"] += 1

        # Extract and validate fields
        rec_label = (parsed.get("recommendation") or "review").lower()
        if rec_label not in {"keep", "review", "archive", "delete"}:
            rec_label = "review"

        try:
            confidence = float(parsed.get("confidence", 0.7))
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))

        reasons = parsed.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = [str(reasons)]

        suggested_action = parsed.get("suggested_action") or None
        if suggested_action:
            suggested_action = str(suggested_action)

        # V1.2 Final: Conservative safety threshold for destructive actions
        # Only allow archive/delete with confidence ≥ 0.6 (combined tier 1 + tier 2)
        if confidence < 0.6 and rec_label in {"archive", "delete"}:
            rec_label = "review"

        return FileLifecycleRecommendation(
            path=path,
            recommendation=rec_label,
            confidence=confidence,
            reasons=reasons,
            suggested_action=suggested_action,
        )

    # ==================== Main Classification Logic ====================

    def classify(
        self,
        use_llm: bool = False,
        llm_client: Optional["LocalLLMClient"] = None,
    ) -> LifecycleResult:
        """
        Classify all files with optional LLM enhancement (V1.2 hybrid-aware).

        Modes:
        - use_llm=False: Pure rule-based (V1 compatibility)
        - use_llm=True + llm_mode="full": Try LLM for every file
        - use_llm=True + llm_mode="hybrid": LLM only for uncertain files

        Returns:
            LifecycleResult with recommendations for each file
        """
        index = self.load_repo_index()
        files = index.get("files", [])
        scan_metadata = index.get("scan_metadata", {})

        # No LLM: pure rule-based (V1 compatibility)
        if not use_llm or llm_client is None or not llm_client.is_available():
            logger.info("LLM disabled or unavailable, using rule-based only")
            recommendations = []
            for entry in files:
                path = entry.get("path", "")
                mtime = float(entry.get("mtime", time.time()))
                age_days = (time.time() - mtime) / 86400
                kind = entry.get("kind", "other")
                rec = self._classify_file(
                    path=path, age_days=age_days, kind=kind, entry=entry
                )
                recommendations.append(rec)
            scan_metadata["classification_method"] = "rule-based-v1"
            return LifecycleResult(
                scan_metadata={
                    "source_index": str(self.index_path),
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "deprecation_days": self.deprecation_days,
                    "confidence_threshold": self.confidence_threshold,
                    **scan_metadata,
                },
                recommendations=recommendations,
            )

        # LLM enabled - V1.2 hybrid mode
        logger.info(f"LLM mode: {self.llm_mode}, max_files={self.llm_max_files}")
        llm_calls = 0

        # Use dict to maintain order stability (architect recommendation)
        by_path: Dict[str, FileLifecycleRecommendation] = {}

        if self.llm_mode == "hybrid":
            # Phase 1: Filter clear cases
            uncertain_entries = []
            for entry in files:
                is_clear, forced_decision = self._is_clear_case(entry)
                if is_clear and forced_decision:
                    rec = FileLifecycleRecommendation(
                        path=entry["path"],
                        recommendation=forced_decision,
                        confidence=0.9,
                        reasons=[f"Rule-based clear case: {forced_decision}"],
                    )
                    by_path[entry["path"]] = rec
                else:
                    uncertain_entries.append(entry)

            # Phase 2: LLM for uncertain (up to limit)
            for entry in uncertain_entries:
                use_llm_for_this = (
                    self.llm_max_files is None or llm_calls < self.llm_max_files
                )

                rec = None
                if use_llm_for_this:
                    self._llm_stats["attempts"] += 1  # CRITICAL: count attempts
                    llm_calls += 1
                    rec = self._classify_with_llm(entry, llm_client)

                if rec is None:
                    # Rule fallback with proper parameters
                    path = entry.get("path", "")
                    mtime = float(entry.get("mtime", time.time()))
                    age_days = (time.time() - mtime) / 86400
                    kind = entry.get("kind", "other")
                    rec = self._classify_file(
                        path=path, age_days=age_days, kind=kind, entry=entry
                    )

                by_path[entry["path"]] = rec

        else:  # "full" mode
            for entry in files:
                self._llm_stats["attempts"] += 1  # CRITICAL: count attempts
                llm_calls += 1
                rec = self._classify_with_llm(entry, llm_client)

                if rec is None:
                    # Rule fallback with proper parameters
                    path = entry.get("path", "")
                    mtime = float(entry.get("mtime", time.time()))
                    age_days = (time.time() - mtime) / 86400
                    kind = entry.get("kind", "other")
                    rec = self._classify_file(
                        path=path, age_days=age_days, kind=kind, entry=entry
                    )

                by_path[entry["path"]] = rec

        # Ensure output order matches input order (for easy diffing V1 vs V1.2)
        recommendations = [by_path[entry["path"]] for entry in files]

        # Statistics consistency check (architect recommendation - helps catch bugs)
        attempts = self._llm_stats.get("attempts", 0)
        successes = self._llm_stats.get("successes", 0)
        fallbacks = self._llm_stats.get("fallbacks", 0)
        if attempts != successes + fallbacks:
            logger.warning(
                "LLM stats mismatch: attempts=%s, successes=%s, fallbacks=%s",
                attempts,
                successes,
                fallbacks,
            )

        # Metadata with V1.2 stats
        result_metadata = {
            "source_index": str(self.index_path),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "deprecation_days": self.deprecation_days,
            "confidence_threshold": self.confidence_threshold,
            "classification_method": "llm-enhanced",
            "llm_usage": llm_client.get_usage_stats(),
            "llm_stats": self._llm_stats,
            "llm_parse": self._llm_parse_stats,
            "llm_mode": self.llm_mode,
            "llm_max_files": self.llm_max_files,
            "llm_calls": llm_calls,
            **scan_metadata,
        }

        return LifecycleResult(
            scan_metadata=result_metadata,
            recommendations=recommendations,
        )

    def _classify_file(
        self, path: str, age_days: float, kind: str, entry: Dict[str, Any]
    ) -> FileLifecycleRecommendation:
        """
        Classify a single file using rule-based logic.

        Future: Replace with LLM-based classification for smarter decisions.
        """
        # Pattern-based rules (highest priority)
        if self._is_archive_pattern(path):
            return FileLifecycleRecommendation(
                path=path,
                recommendation="archive",
                confidence=0.95,
                reasons=["Already in archive directory", "Standard archive pattern"],
                suggested_action=None,  # Already archived
            )

        if self._is_legacy_pattern(path):
            return FileLifecycleRecommendation(
                path=path,
                recommendation="archive",
                confidence=0.9,
                reasons=["Legacy file pattern detected", "Should be preserved"],
                suggested_action=f"Move to docs/archive/{Path(path).parent}/",
            )

        if self._is_backup_pattern(path):
            return FileLifecycleRecommendation(
                path=path,
                recommendation="delete",
                confidence=0.85,
                reasons=["Backup file pattern", "Safe to remove"],
                suggested_action="Delete file (backup copy)",
            )

        # Age-based rules
        if age_days >= self.deprecation_days * 3:
            return FileLifecycleRecommendation(
                path=path,
                recommendation="archive",
                confidence=0.8,
                reasons=[
                    f"Last modified {int(age_days)} days ago",
                    f"Exceeds 3× deprecation threshold ({self.deprecation_days} days)",
                    f"File type: {kind}",
                ],
                suggested_action=f"Move to docs/archive/{Path(path).parent}/",
            )

        if age_days >= self.deprecation_days * 1.5:
            return FileLifecycleRecommendation(
                path=path,
                recommendation="review",
                confidence=0.65,
                reasons=[
                    f"Last modified {int(age_days)} days ago",
                    f"Exceeds 1.5× deprecation threshold ({self.deprecation_days} days)",
                    f"File type: {kind}",
                ],
                suggested_action="Manual review recommended",
            )

        if age_days >= self.deprecation_days:
            return FileLifecycleRecommendation(
                path=path,
                recommendation="review",
                confidence=0.6,
                reasons=[
                    f"Last modified {int(age_days)} days ago",
                    f"Reaches deprecation threshold ({self.deprecation_days} days)",
                ],
                suggested_action=None,
            )

        # Default: keep active files
        return FileLifecycleRecommendation(
            path=path,
            recommendation="keep",
            confidence=0.9,
            reasons=[
                f"Recently modified ({int(age_days)} days ago)",
                f"File type: {kind}",
            ],
            suggested_action=None,
        )

    @staticmethod
    def _is_archive_pattern(path: str) -> bool:
        """Check if file is already in archive directories."""
        archive_patterns = [
            "/archive/",
            "/archived/",
            "/archives/",
            "/legacy/",
            "/deprecated/",
            "/old/",
        ]
        return any(pattern in path.lower() for pattern in archive_patterns)

    @staticmethod
    def _is_legacy_pattern(path: str) -> bool:
        """Check if file matches legacy patterns."""
        legacy_patterns = [
            "_legacy.",
            "-legacy.",
            "_old.",
            "-old.",
            "_deprecated.",
            "-deprecated.",
            "_backup.",
            "-backup.",
        ]
        lower_path = path.lower()
        return any(pattern in lower_path for pattern in legacy_patterns)

    @staticmethod
    def _is_backup_pattern(path: str) -> bool:
        """Check if file is a backup copy."""
        backup_patterns = [".bak", ".backup", "~", ".swp", ".swo", ".orig", ".copy"]
        return any(path.endswith(pattern) for pattern in backup_patterns)

    def save_result(self, result: LifecycleResult) -> None:
        """Save classification results to JSON file."""
        payload = {
            "scan_metadata": result.scan_metadata,
            "recommendations": [
                {
                    "path": r.path,
                    "recommendation": r.recommendation,
                    "confidence": r.confidence,
                    "reasons": r.reasons,
                    "suggested_action": r.suggested_action,
                }
                for r in result.recommendations
            ],
            "summary": self._summarize(result),
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _summarize(result: LifecycleResult) -> Dict[str, Any]:
        """Generate summary statistics."""
        counts: Dict[str, int] = {}
        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0

        for r in result.recommendations:
            counts[r.recommendation] = counts.get(r.recommendation, 0) + 1
            if r.confidence >= 0.8:
                high_confidence += 1
            elif r.confidence >= 0.6:
                medium_confidence += 1
            else:
                low_confidence += 1

        return {
            "total_files": len(result.recommendations),
            "by_decision": counts,
            "confidence_distribution": {
                "high (≥0.8)": high_confidence,
                "medium (0.6-0.8)": medium_confidence,
                "low (<0.6)": low_confidence,
            },
        }


def run_lifecycle_classification(
    index_path: Path,
    output_path: Path,
    deprecation_days: int,
    confidence_threshold: float,
    dry_run: bool = False,
    use_llm: bool = False,  # V1.1+ parameter
    llm_mode: str = "full",  # V1.2 parameter
    llm_max_files: Optional[int] = None,  # V1.2 parameter
) -> None:
    """
    Run lifecycle classification workflow (V1.2 hybrid-aware).

    Args:
        index_path: Path to repo_index.json
        output_path: Where to write lifecycle_recommendations.json
        deprecation_days: Age threshold for deprecation
        confidence_threshold: Minimum confidence for recommendations
        dry_run: If True, only print summary without writing file
        use_llm: Enable LLM-enhanced classification (V1.1+)
        llm_mode: "full" or "hybrid" mode (V1.2)
        llm_max_files: Max LLM calls in hybrid mode (V1.2)
    """
    # Initialize LLM client if requested (V1.1+)
    # V2.0: Prefer LIR client for batching, concurrency, and thermal management
    import os
    llm_client = None
    disable_lir = os.environ.get("CODEWIKI_DISABLE_LIR") == "true"
    
    if use_llm:
        # Try LIR client first (better performance), unless disabled
        if HAS_LIR_CLIENT and not disable_lir:
            try:
                # Map llm_mode to LIR policy
                lir_policy = "balanced"
                if llm_mode == "full":
                    lir_policy = "performance"
                elif llm_max_files and llm_max_files <= 30:
                    lir_policy = "silent"
                
                llm_client = LIRLocalLLMClient(policy=lir_policy)
                if llm_client.is_available():
                    logger.info("Using LIR client (policy=%s)", lir_policy)
                else:
                    logger.warning("LIR unavailable, trying legacy client")
                    llm_client = None
            except Exception as e:
                logger.warning("Failed to initialize LIR client: %s", e)
                llm_client = None
        
        # Fallback to legacy client
        if llm_client is None and HAS_LLM_CLIENT:
            try:
                llm_client = LocalLLMClient()
                if not llm_client.is_available():
                    logger.warning("Legacy LLM client unavailable, fallback to rules")
                    use_llm = False
            except Exception as e:
                logger.error("Failed to initialize LLM client: %s", e)
                use_llm = False
        
        if llm_client is None:
            logger.warning("No LLM client available, fallback to rules")
            use_llm = False

    classifier = LifecycleClassifier(
        index_path=index_path,
        output_path=output_path,
        deprecation_days=deprecation_days,
        confidence_threshold=confidence_threshold,
        llm_mode=llm_mode,
        llm_max_files=llm_max_files,
    )

    print(f"📋 [code-wiki] Loading repo index from {index_path}...")
    result = classifier.classify(use_llm=use_llm, llm_client=llm_client)

    summary = classifier._summarize(result)

    if dry_run:
        print("🔍 [code-wiki] Lifecycle Classification Preview")
        print(f"   Total files: {summary['total_files']}")
        print("   Recommendations:")
        for decision, count in summary["by_decision"].items():
            print(f"     - {decision}: {count}")
        print("   Confidence distribution:")
        for level, count in summary["confidence_distribution"].items():
            print(f"     - {level}: {count}")
        print(f"\n   Would write to: {output_path}")
        return

    classifier.save_result(result)
    print(f"✅ [code-wiki] Lifecycle recommendations written to {output_path}")
    print(f"   Total files analyzed: {summary['total_files']}")
    print("   Recommendations:")
    for decision, count in summary["by_decision"].items():
        print(f"     - {decision}: {count}")
