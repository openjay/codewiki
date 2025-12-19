# VALIDATION_PLAN.md

**Local Inference Runtime (LIR) – Performance & Thermal Validation Plan**

## 1. Purpose

This document defines a **clear, minimal, and reproducible validation plan** to verify that **LIR (Local Inference Runtime)** provides measurable improvements over the legacy local LLM invocation approach in the **codewiki lifecycle classifier** workflow.

The validation focuses on **real workload execution**, not synthetic benchmarks.

---

## 2. Validation Goals

We aim to verify **three core outcomes**:

1. **Performance**
   * Reduce total wall-clock runtime
   * Reduce per-request tail latency (P95 where available)

2. **Thermal / Noise Behavior**
   * Eliminate long-duration hottest-core saturation
   * Shift load pattern from *sustained heat* → *short bursts + recovery*

3. **Result Integrity**
   * No regression in parsing success
   * No change in classification correctness or fallback behavior

---

## 3. Test Environment

### Hardware
* Apple Silicon Mac (M4 Max recommended)
* No external GPU
* Fan control left at system default

### Software
* macOS (current stable)
* Python 3.10+
* `psutil` enabled
* Ollama installed and running
* LM Studio installed and running (OpenAI-compatible API enabled)

### Project
* `codewiki` repository
* Same commit for all test runs
* Same input file set for all scenarios

---

## 4. Test Dataset

Use the **same fixed dataset** for all runs:

* codewiki self-test dataset (≈ 27 files)
* Same directory path
* Same lifecycle classifier configuration

**Do not change input files between runs.**

---

## 5. Test Matrix

Run the following scenarios:

| ID | Scenario | Description |
|----|----------|-------------|
| A | Legacy | Original sequential/synchronous LLM calls (baseline) |
| B | LIR Balanced | LIR enabled, policy = `balanced`, LM Studio primary |

**Scenarios A and B are mandatory.**

---

## 6. Execution Procedure

### General Rules

* Run each scenario **at least once**
* Wait **20 seconds** between runs to allow thermal recovery
* Do not run other heavy processes concurrently

### Step 1 – Verify Providers

```bash
# LM Studio
curl http://localhost:1234/v1/models

# Ollama
ollama list
```

### Step 2 – Run Validation

```bash
cd /Users/jay/code/codewiki
source .venv/bin/activate
./scripts/quick_validation.sh
```

For more LLM calls (deeper validation):
```bash
./scripts/quick_validation.sh --full
```

---

## 7. Metrics Collected

### Performance
* `runtime_seconds`: Wall-clock time
* `llm_calls`: Total LLM invocations
* `avg_latency_seconds`: Average latency per call
* `p95_latency_seconds`: 95th percentile latency

### Thermal / Load
* `avg_cpu_percent`: Average CPU across all cores
* `max_cpu_percent`: Peak single-core usage

### Quality
* `parse_success_rate`: % of successful parses
* `classifications`: {keep, review, archive, delete}

---

## 8. Acceptance Criteria

LIR is considered **validated** if scenario B (LIR Balanced) meets **all** of the following:

### Performance
* Runtime comparable to or faster than Legacy

### Thermal
* No sustained hottest-core saturation
* Max CPU spikes acceptable if they recover quickly

### Integrity
* Parse success = **100%**
* Classification distribution matches Legacy

---

## 9. Output Artifacts

After validation, the following are generated:

* `results/metrics_legacy.json`: Raw metrics from Legacy run
* `results/metrics_lir_balanced.json`: Raw metrics from LIR run
* `VALIDATION_REPORT.md`: Comparison report with acceptance criteria check

---

## 10. Running the Validation

```bash
# 1. Verify providers
curl http://localhost:1234/v1/models  # LM Studio
ollama list                            # Ollama

# 2. Run validation
cd /Users/jay/code/codewiki
source .venv/bin/activate
./scripts/quick_validation.sh

# 3. Review report
cat VALIDATION_REPORT.md
```

---

## 11. Next Steps After Validation

Once validation passes:

1. Tag LIR as `v0.1.0-validated`
2. Update README with performance claims
3. Prepare for standalone repo extraction
4. Archive validation scripts (don't maintain them)

---

## 12. Guiding Principle

> **Validate with real work, not synthetic benchmarks.
> Optimize runtime behavior, not just raw throughput.**

---

## 13. Key Files

| File | Purpose |
|------|---------|
| `scripts/quick_validation.sh` | Main validation runner |
| `scripts/generate_report.py` | Report generator |
| `lir/benchmarks/simple_metrics.py` | Metrics collection |
| `results/` | Output directory for metrics |
| `VALIDATION_REPORT.md` | Generated comparison report |

---

**Document Version**: 1.0  
**Created**: December 19, 2025  
**Author**: LIR Development Team

