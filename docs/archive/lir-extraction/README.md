# LIR Extraction Archive

This directory contains historical documentation and validation results from the extraction of LIR (Local Inference Runtime) from the codewiki project.

## What is LIR?

LIR is a lightweight, OpenAI-compatible optimization layer for local LLM inference. It was originally developed as part of codewiki to solve thermal management and performance issues with local LLM calls.

**LIR is now a standalone project**: https://github.com/openjay/lir

## What's in This Archive?

### Validation Results (`validation-results/`)

Benchmark data proving LIR's performance improvements:

- **stress_legacy_c1.json** - Baseline performance (sequential, no LIR)
- **stress_lir_c1.json** - LIR performance (sequential, c=1)
- **stress_lir_c4.json** - LIR performance (concurrent, c=4)
- **metrics_legacy.json** - Quick validation baseline
- **metrics_lir_balanced.json** - Quick validation with LIR
- **log_*.txt** - Detailed execution logs

**Key Results**:
- 2.85x throughput improvement (sequential workloads)
- 2.46x throughput improvement (concurrent workloads)
- 8.9x better P50 latency (0.96s vs 8.52s)
- Reduced thermal load and fan noise

### Documentation

- **VALIDATION_REPORT.md** - Final validation results and acceptance criteria
- **VALIDATION_PLAN.md** - Validation methodology and test plan
- **FAN_NOISE_ANALYSIS_SUMMARY.md** - Thermal behavior analysis
- **FAN_NOISE_QUICK_REFERENCE.md** - Quick reference for fan noise issues
- **LLM_PERFORMANCE_ANALYSIS.md** - Detailed performance analysis

## Why Archive This?

These results document the **evidence-based extraction** of LIR from codewiki:

1. **Historical Record**: Shows why LIR was created and extracted
2. **Validation Evidence**: Proves LIR provides real benefits (not just theoretical)
3. **Methodology**: Documents the "steady-state" validation approach
4. **Benchmark Baseline**: Provides comparison point for future improvements

## Current State (Post-Extraction)

As of v2.0, codewiki is a **consumer** of LIR, not a container:

- LIR is installed as an external dependency: `pip install -e ../lir`
- Codewiki uses LIR via the adapter in `codewiki/llm_client_lir.py`
- All LIR implementation, tests, and benchmarks now live in the LIR repo

See [LIR Integration Guide](../../LIR_INTEGRATION_GUIDE.md) for current usage.

## For Current Benchmarks

This archive contains **historical** results from the extraction process.

For **current** LIR benchmarks and performance data, see:
- https://github.com/openjay/lir#benchmark-results
- LIR repo: `benchmarks/` directory

## Timeline

- **Dec 19, 2025**: LIR extraction completed
- **Dec 19, 2025**: Validation results archived
- **Dec 20, 2025**: Codewiki cleanup completed

---

*This archive is preserved for historical reference and should not be modified.*

