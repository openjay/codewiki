# Code Wiki V1.2 Testing Guide

## Quick Start Testing

### Prerequisites

- ✅ V1.2 implementation is complete
- ✅ V1 compatibility verified (0.15s, rule-based-v1, 662 keep / 2 archive)
- ⏳ LM Studio or Ollama running (for LLM tests)

## Test Sequence

### Test 1: V1 Baseline (✅ PASSED)

```bash
# Ensure config has use_llm: false
make code-wiki-lifecycle
```

**Result:**
```
✅ Runtime: 0.15s
✅ Method: rule-based-v1
✅ Files: 664
✅ Keep: 662, Archive: 2
```

### Test 2: V1.2 Full Mode (JSON Parse Improvements)

**Setup:**
1. Start LM Studio with `llama-3.2-3b-instruct`
2. Edit `config/code_wiki_config.yaml`:
   ```yaml
   lifecycle_classifier:
     use_llm: true
     llm_mode: "full"
   ```

**Run:**
```bash
make code-wiki-lifecycle
```

**Expected Results:**
- Runtime: ~7 min (baseline from V1.1)
- LLM calls: 664 (all files)
- Parse success rate: 90%+ (improved from V1.1's 78%)

**Verify:**
```bash
cat data/code_wiki/lifecycle_recommendations.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
meta = d['scan_metadata']
print(f\"Method: {meta['classification_method']}\")
print(f\"LLM calls: {meta['llm_calls']}\")
print(f\"Parse success: {meta['llm_parse']['parse_success']}\")
print(f\"Parse attempts: {meta['llm_parse']['attempts']}\")
print(f\"Parse rate: {meta['llm_parse']['parse_success'] / meta['llm_parse']['attempts']:.1%}\")
print(f\"\\nRecommendations:\")
for k, v in d['summary']['by_decision'].items():
    print(f\"  {k}: {v}\")
"
```

**Success Criteria:**
- ✅ Parse rate > 90%
- ✅ Temperature: 0.3 (check logs)
- ✅ Max tokens: 500 (check logs)
- ✅ Conservative recommendations (more "review" than "delete")

### Test 3: V1.2 Hybrid Mode (Performance Optimization)

**Setup:**
1. Edit `config/code_wiki_config.yaml`:
   ```yaml
   lifecycle_classifier:
     use_llm: true
     llm_mode: "hybrid"
     llm_max_files: 150
   ```

**Run:**
```bash
time make code-wiki-lifecycle
```

**Expected Results:**
- Runtime: 2-3 min (60% faster than full mode)
- LLM calls: ~150 (77% reduction)
- Clear cases: ~514 files (handled by rules)
- Review count: <300 (more targeted)

**Verify:**
```bash
cat data/code_wiki/lifecycle_recommendations.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
meta = d['scan_metadata']
print(f\"Mode: {meta['llm_mode']}\")
print(f\"LLM calls: {meta['llm_calls']} / {meta['llm_max_files']} max\")
print(f\"Clear cases: ~{664 - meta['llm_calls']} files\")
print(f\"Parse success: {meta['llm_parse']['parse_success']} / {meta['llm_parse']['attempts']}\")
print(f\"Parse rate: {meta['llm_parse']['parse_success'] / meta['llm_parse']['attempts']:.1%}\")
print(f\"\\nRecommendations:\")
summary = d['summary']['by_decision']
for k, v in summary.items():
    print(f\"  {k}: {v}\")
print(f\"\\nReview ratio: {summary.get('review', 0) / 664:.1%}\")
"
```

**Success Criteria:**
- ✅ LLM calls ~150 (not 664)
- ✅ Runtime < 3 min
- ✅ Review count < 300 (more reasonable than V1.1's 426)
- ✅ Parse rate > 90%

### Test 4: Ollama Sanity Check (Optional)

**Setup:**
1. Edit `config/llm_providers.json`:
   ```json
   {
     "provider": "ollama",
     "priority": 1,
     "model": "qwen3:8b"
   }
   ```
2. Ensure Ollama is running: `curl http://localhost:11434/api/tags`

**Run:**
```bash
make code-wiki-lifecycle
```

**Expected Results:**
- Provider: ollama
- Model: qwen3:8b
- Parse rate: 95%+ (typically better than LM Studio)

**Verify:**
```bash
cat data/code_wiki/lifecycle_recommendations.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
usage = d['scan_metadata']['llm_usage']
print(f\"Provider: {usage['provider']}\")
print(f\"Model: {usage['model']}\")
print(f\"Parse rate: {d['scan_metadata']['llm_parse']['parse_success'] / d['scan_metadata']['llm_parse']['attempts']:.1%}\")
"
```

## Comparison Analysis

After running all tests, compare results:

```bash
# Create comparison report
python3 << 'EOF'
import json
from pathlib import Path

results = []
for test in ["v1_baseline", "v1_2_full", "v1_2_hybrid", "ollama"]:
    path = Path(f"data/code_wiki/test_results_{test}.json")
    if path.exists():
        data = json.loads(path.read_text())
        results.append({
            "Test": test,
            "Method": data["scan_metadata"]["classification_method"],
            "LLM Calls": data["scan_metadata"].get("llm_calls", 0),
            "Parse Rate": f"{data['scan_metadata'].get('llm_parse', {}).get('parse_success', 0) / max(data['scan_metadata'].get('llm_parse', {}).get('attempts', 1), 1):.1%}",
            "Keep": data["summary"]["by_decision"].get("keep", 0),
            "Review": data["summary"]["by_decision"].get("review", 0),
            "Archive": data["summary"]["by_decision"].get("archive", 0),
        })

print("| Test | Method | LLM Calls | Parse Rate | Keep | Review | Archive |")
print("|------|--------|-----------|------------|------|--------|---------|")
for r in results:
    print(f"| {r['Test']} | {r['Method']} | {r['LLM Calls']} | {r['Parse Rate']} | {r['Keep']} | {r['Review']} | {r['Archive']} |")
EOF
```

## Troubleshooting

### Issue: "LLM client not available"

```bash
# Check LM Studio
curl http://localhost:1234/v1/models

# Check Ollama
curl http://localhost:11434/api/tags
```

**Solution:** Ensure provider is running and model is loaded.

### Issue: Low parse success rate (<80%)

**Possible causes:**
1. Wrong model loaded (use llama-3.2-3b-instruct or qwen3:8b)
2. Temperature not reduced (should be 0.3, not 0.7)
3. Max tokens not reduced (should be 500, not 2000)

**Verify:**
```bash
# Check LLM client settings
grep -A2 "temperature\|max_tokens\|num_predict" scripts/documentation/llm_client.py
```

### Issue: Hybrid mode calling LLM for all files

**Check config:**
```yaml
llm_mode: "hybrid"  # NOT "full"
llm_max_files: 150
```

**Verify clear-case detection:**
```bash
# Add debug logging to _is_clear_case()
# Should filter ~75% of files (514 out of 664)
```

## Documentation Check

After testing, update these files:

1. **`CODE_WIKI_V1.2_HYBRID_COMPLETE.md`**
   - Fill in actual test results
   - Update status from "⏳ Ready" to "✅ PASSED"

2. **`CODE_WIKI_V1.1_LLM_INTEGRATION_COMPLETE.md`**
   - Add V1.2 section with hybrid mode overview
   - Link to V1.2 completion doc

3. **`CODE_WIKI_LLM_INTEGRATION_GUIDE.md`**
   - Update usage examples for hybrid mode
   - Add performance comparison table

## Success Checklist

- [ ] V1 baseline confirmed (0.15s, rule-based)
- [ ] V1.2 full mode tested (parse rate >90%)
- [ ] V1.2 hybrid mode tested (LLM calls ~150, runtime 2-3 min)
- [ ] Both providers tested (LM Studio + Ollama)
- [ ] Review count reasonable (<300 files)
- [ ] Documentation updated with actual results
- [ ] Comparison table created

---

**Ready to test!** Start with Test 2 (full mode) to validate JSON parsing improvements, then Test 3 (hybrid mode) for performance optimization.
