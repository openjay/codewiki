# LIR Integration Guide

## Overview

Codewiki uses [LIR (Local Inference Runtime)](https://github.com/openjay/lir) for optimized local LLM inference.

LIR provides intelligent scheduling, batching, and thermal management for local LLM calls, resulting in significant performance improvements and reduced fan noise.

## Installation

### Development (Editable Install)

```bash
# Install LIR as editable dependency from local clone
pip install -e ../lir
```

### Production (Git Install)

```bash
# Install from GitHub
pip install git+https://github.com/openjay/lir.git@v0.1.0

# Or install specific version
pip install git+https://github.com/openjay/lir.git@v0.1.1
```

## Configuration

LIR is configured via environment variables and config files.

### Environment Variables

Control LIR behavior at runtime:

```bash
# Enable/disable LIR (default: true if installed)
export CODEWIKI_USE_LIR=true

# Set LIR policy: silent/balanced/performance (default: balanced)
export CODEWIKI_LIR_POLICY=balanced

# Force disable LIR (useful for testing)
export CODEWIKI_DISABLE_LIR=true

# Limit number of files processed with LLM (default: 30)
export CODEWIKI_LLM_MAX_FILES=30
```

### Provider Configuration

Configure LLM providers in `config/llm_providers.json`:

```json
{
  "providers": [
    {
      "name": "lm_studio",
      "base_url": "http://localhost:1234",
      "model": "llama-3.2-3b-instruct",
      "priority": 1,
      "timeout": 60
    },
    {
      "name": "ollama",
      "base_url": "http://localhost:11434",
      "model": "qwen3:8b",
      "priority": 2,
      "timeout": 60
    }
  ]
}
```

**Priority**: Lower number = higher priority. LIR will prefer providers with lower priority numbers.

### LIR Policies

LIR supports three built-in policies:

| Policy | Concurrency | Batching | Use Case |
|--------|-------------|----------|----------|
| `silent` | 1 | 100ms window | Minimize fan noise |
| `balanced` | 3 | 40ms window | General use (default) |
| `performance` | 6 | 20ms window | Maximum throughput |

## Usage

### Automatic Integration

LIR is automatically used when available. Codewiki falls back to the legacy client if LIR is not installed.

The integration happens transparently in [`codewiki/llm_client_lir.py`](../codewiki/llm_client_lir.py).

### Running Codewiki with LIR

```bash
# Standard usage (LIR enabled by default)
codewiki scan /path/to/repo

# Force legacy client
CODEWIKI_DISABLE_LIR=true codewiki scan /path/to/repo

# Use performance policy
CODEWIKI_LIR_POLICY=performance codewiki scan /path/to/repo

# Use silent policy (quieter fans)
CODEWIKI_LIR_POLICY=silent codewiki scan /path/to/repo
```

## Performance

LIR provides significant performance improvements over the legacy sequential approach:

| Metric | Legacy | LIR (Sequential) | LIR (Concurrent) | Improvement |
|--------|--------|------------------|------------------|-------------|
| **Throughput** | 7.3 calls/min | 20.8 calls/min | 18.0 calls/min | **2.85x** |
| **P50 Latency** | 8.52s | 0.96s | 0.80s | **8.9x better** |
| **P95 Latency** | 8.70s | 1.03s | 1.04s | **8.4x better** |
| **Thermal Load** | High sustained | Reduced bursts | Reduced bursts | Quieter |

*Results from stress test with 50 LLM calls on Apple Silicon (M4 Max)*

### Why LIR is Faster

1. **Connection Pooling**: Reuses HTTP connections instead of creating new ones for each request
2. **Micro-batching**: Combines multiple requests to reduce overhead
3. **Thermal Management**: Prevents CPU throttling by managing thermal load
4. **Intelligent Scheduling**: Optimizes request ordering and concurrency

See [LIR benchmarks](https://github.com/openjay/lir#benchmark-results) for detailed performance data.

## Troubleshooting

### Check if LIR is Available

```bash
python -c "from codewiki.llm_client_lir import HAS_LIR; print(f'LIR available: {HAS_LIR}')"
```

**Expected output**: `LIR available: True`

### Check LIR Status

```python
from codewiki.llm_client_lir import LIRLocalLLMClient

client = LIRLocalLLMClient()
print(f"LIR available: {client.is_available()}")
```

### Verify Provider Connectivity

```bash
# Check LM Studio
curl http://localhost:1234/v1/models

# Check Ollama
curl http://localhost:11434/api/tags
```

### Common Issues

**Issue**: `LIR available: False`

**Solution**: Install LIR:
```bash
pip install -e ../lir
# or
pip install git+https://github.com/openjay/lir.git@v0.1.0
```

**Issue**: High fan noise

**Solution**: Use `silent` policy:
```bash
CODEWIKI_LIR_POLICY=silent codewiki scan /path/to/repo
```

**Issue**: Slow performance

**Solution**: 
1. Check provider connectivity (see above)
2. Try `performance` policy
3. Ensure LM Studio is using a fast model (3B parameters recommended)

## Architecture

```
┌─────────────────────┐
│   Codewiki CLI      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ llm_client_lir.py   │ ◄── Adapter (sync wrapper)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   LIR Package       │ ◄── External dependency
│  (pip install -e)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Ollama / LM Studio │ ◄── Local LLM providers
└─────────────────────┘
```

## Implementation Details

The LIR integration in codewiki consists of:

1. **Adapter** ([`codewiki/llm_client_lir.py`](../codewiki/llm_client_lir.py)): Wraps LIR's async client in a synchronous interface
2. **Fallback**: Automatically falls back to legacy client if LIR is unavailable
3. **Configuration**: Reads environment variables and config files
4. **Lifecycle Classifier** ([`codewiki/lifecycle_classifier.py`](../codewiki/lifecycle_classifier.py)): Uses LIR client for LLM calls

## Migration from Legacy Client

If you're migrating from the legacy client:

1. **No code changes required** - LIR is used automatically when installed
2. **Test with small dataset** - Start with a few files to verify behavior
3. **Monitor performance** - Use environment variables to tune policy
4. **Keep legacy as fallback** - LIR gracefully falls back if unavailable

## Further Reading

- [LIR GitHub Repository](https://github.com/openjay/lir)
- [LIR README](https://github.com/openjay/lir#readme)
- [LIR Benchmarks](https://github.com/openjay/lir#benchmark-results)
- [Codewiki LLM Integration Guide](CODE_WIKI_LLM_INTEGRATION_GUIDE.md)
- [LIR Extraction Archive](archive/lir-extraction/README.md) - Historical validation data

## Support

For LIR-specific issues, please file an issue on the [LIR repository](https://github.com/openjay/lir/issues).

For codewiki integration issues, file an issue on the [codewiki repository](https://github.com/openjay/codewiki/issues).

