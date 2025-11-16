# Code Wiki V1.2 - Operational Guide

**Version**: V1.2 Final  
**Last Updated**: 2025-11-16  
**Status**: Production Ready

---

## Quick Start

### Default (Safe) Mode - Rule-Based Only

```bash
# 1. Scan repository
make code-wiki-scan

# 2. Classify files (rule-based, no LLM)
make code-wiki-lifecycle

# 3. View results
python3 scripts/documentation/inspect_lifecycle_result.py
```

**When to use**: Daily/CI checks, quick scans, no LLM dependencies needed.

---

## LLM-Enhanced Mode (V1.2 Hybrid)

### Prerequisites

1. **Start Local LLM Provider**:
   ```bash
   # Option 1: Ollama (recommended for accuracy)
   ollama serve  # Ensure qwen3:8b is installed
   
   # Option 2: LM Studio (recommended for speed)
   # Start LM Studio GUI and load model
   ```

2. **Verify Provider Health**:
   ```bash
   curl http://localhost:11434/api/tags        # Ollama
   curl http://localhost:1234/v1/models        # LM Studio
   ```

### Operational Profiles

#### Profile 1: Daily / Pre-Commit (Fast)

**Use Case**: Quick checks, CI integration, frequent scans  
**Runtime**: ~1 min (with LM Studio)  
**LLM Calls**: 50-80 files

**Configuration**:
```yaml
# config/code_wiki_config.yaml
lifecycle_classifier:
  use_llm: true
  llm_mode: "hybrid"
  llm_max_files: 80
```

**Run**:
```bash
make code-wiki-scan
make code-wiki-lifecycle
python3 scripts/documentation/inspect_lifecycle_result.py
```

**Remember**: Revert to `use_llm: false` after running!

---

#### Profile 2: Weekly / Deep Review (Recommended)

**Use Case**: Comprehensive cleanup, periodic maintenance  
**Runtime**: ~20 min (Ollama) / ~2-3 min (LM Studio)  
**LLM Calls**: 150 files

**Configuration**:
```yaml
# config/code_wiki_config.yaml
lifecycle_classifier:
  use_llm: true
  llm_mode: "hybrid"
  llm_max_files: 150
```

**Run**:
```bash
make code-wiki-scan
make code-wiki-lifecycle
python3 scripts/documentation/inspect_lifecycle_result.py
```

**Remember**: Revert to `use_llm: false` after running!

---

#### Profile 3: Audit / Exhaustive (Full Scan)

**Use Case**: Major refactoring, complete repository audit  
**Runtime**: ~140 min (Ollama) / ~15 min (LM Studio)  
**LLM Calls**: All files (~664)

**Configuration**:
```yaml
# config/code_wiki_config.yaml
lifecycle_classifier:
  use_llm: true
  llm_mode: "full"
  llm_max_files: null  # or comment out
```

**Run**:
```bash
make code-wiki-scan
make code-wiki-lifecycle
python3 scripts/documentation/inspect_lifecycle_result.py
```

**Remember**: Revert to `use_llm: false` and `llm_mode: "hybrid"` after running!

---

## Best Practices

### 1. Safe Default Configuration

**Always keep the default as**:
```yaml
use_llm: false
llm_mode: "hybrid"
llm_max_files: 150
```

**Why**: 
- Prevents accidental LLM calls in CI/automation
- No external dependencies for basic functionality
- Rule-based mode is sufficient for most cases

### 2. Manual LLM Activation

**Before LLM run**:
1. Manually edit `config/code_wiki_config.yaml`
2. Set `use_llm: true`
3. Choose appropriate profile (50-80 / 150 / null)
4. Verify LLM provider is running

**After LLM run**:
1. Review results with `inspect_lifecycle_result.py`
2. Manually revert `use_llm: false`
3. Commit results if satisfied

### 3. Choosing Provider

**Ollama (qwen3:8b)**:
- ✅ Better accuracy (85% parse success)
- ✅ More conservative recommendations
- ⚠️ Slower (~8s per file)
- **Use for**: Production cleanup, important decisions

**LM Studio (llama-3.2-3b-instruct)**:
- ✅ Much faster (~1-2s per file)
- ✅ Good enough for routine checks
- ⚠️ Slightly lower accuracy (~78% parse success)
- **Use for**: Daily scans, quick checks, CI integration

**Configure Priority**:
```json
// config/llm_providers.json
{
  "providers": [
    {
      "provider": "ollama",
      "priority": 1  // Lower = higher priority
    },
    {
      "provider": "lm_studio",
      "priority": 2
    }
  ]
}
```

### 4. Reviewing Results

**Quick Check**:
```bash
python3 scripts/documentation/inspect_lifecycle_result.py
```

**Detailed Review**:
```bash
python3 scripts/documentation/inspect_lifecycle_result.py --verbose
```

**Manual Inspection**:
```bash
cat data/code_wiki/lifecycle_recommendations.json | jq '.summary'
```

---

## Configuration Reference

### LLM Sampling Parameters (Advanced)

**Current Settings** (optimized for structured JSON):
```python
# scripts/documentation/llm_client.py
temperature: 0.1   # Ultra-stable, minimal creativity
max_tokens: 400    # Concise output
```

**If you need adjustments**:
- **More conservative**: `temperature: 0.05` (even more deterministic)
- **More creative**: `temperature: 0.2` (if LLM seems "too rigid")
- **Longer output**: `max_tokens: 500` (if JSON gets truncated)

### Safety Thresholds

**Current Multi-Tier Safety**:
```python
# Tier 1: Very low confidence (<0.4) → always review
# Tier 2: Medium-low confidence (<0.6) → still review
# Only allow archive/delete with confidence ≥ 0.6
```

**To adjust** (edit `scripts/documentation/lifecycle_classifier.py`):
- More conservative: Change `0.6` → `0.7` or `0.8`
- More aggressive: Change `0.6` → `0.5` (not recommended)

---

## Troubleshooting

### Issue: "LLM client not available"

**Cause**: Provider not running or not reachable  
**Fix**:
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check LM Studio
curl http://localhost:1234/v1/models

# Restart provider if needed
```

### Issue: High parse failure rate (>20%)

**Cause**: LLM output too verbose or inconsistent  
**Fix**:
1. Reduce `temperature` (0.1 → 0.05)
2. Reduce `max_tokens` (400 → 300)
3. Check LLM model is loaded correctly
4. Try different provider (Ollama vs LM Studio)

### Issue: Too many "review" recommendations

**Cause**: LLM being overly conservative  
**Fix**:
1. Check if clear-case detection is working (`llm_calls` should be ~20-25% of total files)
2. Increase `llm_max_files` to let LLM analyze more uncertain files
3. Review recommendations manually - many may be valid

### Issue: Script takes too long

**Cause**: Using Ollama with high `llm_max_files`  
**Fix**:
1. Switch to LM Studio (priority: 1)
2. Reduce `llm_max_files` (150 → 80)
3. Use daily profile for frequent scans

---

## Metrics & Performance

### Expected Performance (V1.2 Hybrid, 150 files)

| Metric | Ollama (qwen3:8b) | LM Studio (llama-3.2-3b) |
|--------|-------------------|--------------------------|
| **Runtime** | ~20 min | ~2-3 min |
| **Parse Success** | 85% | ~78% |
| **Token Usage** | ~39k | ~35k |
| **Recommendation Quality** | More conservative | More aggressive |

### Health Metrics to Monitor

**Good Signs**:
- ✅ Parse success rate ≥ 80%
- ✅ Review count < 300 (ideally < 50)
- ✅ Zero delete recommendations (safety working)
- ✅ Fallback count > 0 (graceful degradation working)

**Warning Signs**:
- ⚠️ Parse success < 75% → check LLM health
- ⚠️ Review count > 400 → LLM too conservative, check clear-case detection
- ⚠️ Delete count > 10 → safety thresholds may need adjustment

---

## Advanced Usage

### Preview Mode (Dry Run)

```bash
# See what would change without writing files
python3 scripts/documentation/code_wiki_orchestrator.py --mode lifecycle --preview
```

### Custom Configuration

```bash
# Use non-default config file
export CODE_WIKI_CONFIG=/path/to/custom/config.yaml
make code-wiki-lifecycle
```

### Integration with CI/CD

**GitHub Actions Example**:
```yaml
name: Code Wiki Check
on: [pull_request]

jobs:
  lifecycle-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Code Wiki (Rule-Based)
        run: |
          make code-wiki-scan
          make code-wiki-lifecycle  # use_llm: false by default
      - name: Check for new reviews
        run: |
          python3 scripts/documentation/inspect_lifecycle_result.py
```

---

## Maintenance

### Regular Tasks

**Weekly** (recommended):
1. Run Profile 2 (Weekly/Deep Review)
2. Review flagged files
3. Update/archive as needed
4. Commit updated recommendations

**Monthly** (optional):
1. Review LLM parse success rates
2. Adjust clear-case thresholds if needed
3. Update operational profiles based on repo growth

**Quarterly** (optional):
1. Run Profile 3 (Audit/Exhaustive)
2. Deep clean deprecated files
3. Update documentation

---

## Security & Privacy

**Local LLM Benefits**:
- ✅ No data leaves your machine
- ✅ No API costs
- ✅ No rate limits
- ✅ Full control over model and parameters

**Data Flow**:
1. Code Wiki scans repository metadata only (paths, sizes, dates)
2. No actual code content is sent to LLM (only metadata)
3. All results stored locally in `data/code_wiki/`

---

## Support & Feedback

**Documentation**:
- Implementation: `docs/workflows/CODE_WIKI_V1.2_HYBRID_COMPLETE.md`
- Testing Guide: `docs/workflows/CODE_WIKI_V1.2_TESTING_GUIDE.md`
- Test Results: `docs/workflows/CODE_WIKI_V1.2_TEST_RESULTS.md`

**Quick Reference**:
- Summary: `CODE_WIKI_V1.2_IMPLEMENTATION_SUMMARY.md`
- Design: `docs/workflows/CODE_WIKI_DESIGN.md`

---

## Version History

**V1.2 Final (2025-11-16)**:
- ✅ Hybrid mode with clear-case detection
- ✅ Multi-tier safety thresholds (0.4 / 0.6)
- ✅ Optimized LLM parameters (temp=0.1, tokens=400)
- ✅ Operational profiles (daily/weekly/audit)
- ✅ Inspection utility script
- ✅ Production validated (85% parse success, 99% fewer reviews)

**V1.1 (2025-11-15)**:
- ✅ Full LLM mode with Ollama + LM Studio
- ✅ Priority-based provider selection
- ✅ Graceful fallback

**V1.0 (2025-11-14)**:
- ✅ Rule-based classification
- ✅ Repository scanner
- ✅ Documentation generator

---

**Status**: ✅ **PRODUCTION READY**  
**Recommended Profile**: Weekly/Deep Review (150 files, hybrid mode)  
**Default Config**: `use_llm: false` (safe, no dependencies)
