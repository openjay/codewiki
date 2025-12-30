# CodeWiki

**LLM-enhanced code lifecycle analysis and documentation generator**

CodeWiki helps you maintain clean codebases by automatically analyzing files, classifying their lifecycle status, and generating up-to-date documentation.

## Features

- 🔍 **Repository Scanning**: Comprehensive codebase analysis with metadata extraction
- 🤖 **Multi-Provider LLM Support**: Use any LLM provider - local or cloud, with flexible configuration
  - Local: Ollama, LM Studio (100% private, no API keys)
  - Cloud: OpenAI, Anthropic, Groq, or any OpenAI-compatible API (opt-in)
  - Auto-detects API format (Ollama vs OpenAI-compatible)
  - Priority-based failover for reliability
- ⚡ **Local Inference Optimization**: Powered by [LIR](https://github.com/openjay/lir) for 2.85x faster inference
- 🧠 **Reasoning Model Support**: Handles advanced models with `<think>` tag parsing
- 🎯 **Hybrid Mode**: Smart file selection (77% fewer LLM calls vs full mode)
- 🛡️ **Privacy-First Design**: 100% local by default, cloud providers disabled until explicitly enabled
- 📊 **Automatic Documentation**: Generates markdown docs with architecture overviews
- 📈 **Operational Profiles**: Daily/Weekly/Audit modes for different use cases

## Installation

```bash
# Install from source
git clone https://github.com/openjay/codewiki.git
cd codewiki
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Start your local LLM (Ollama or LM Studio)
ollama serve  # or start LM Studio GUI

# 2. Run lifecycle classification (rule-based, safe default)
codewiki --mode lifecycle

# 3. Enable LLM enhancement (edit config/code_wiki_config.yaml: use_llm: true)
codewiki --mode lifecycle

# 4. Inspect results
python -m codewiki.inspect_lifecycle_result
```

## Operational Profiles

CodeWiki supports three operational profiles:

### Daily / Pre-Commit (Default)
- **LLM calls**: 50-80 files
- **Runtime**: ~1 min
- **Use case**: Fast scans, CI checks
- **Config**: `llm_max_files: 80`

### Weekly / Deep Review
- **LLM calls**: 150 files
- **Runtime**: ~2-3 min (LM Studio) / ~20 min (Ollama)
- **Use case**: Comprehensive cleanup
- **Config**: `llm_max_files: 150`

### Audit / Exhaustive
- **LLM calls**: All files
- **Runtime**: ~15 min (LM Studio) / ~140 min (Ollama)
- **Use case**: Major refactoring, full audit
- **Config**: `llm_mode: "full"`, `llm_max_files: null`

## Multi-Provider Configuration

CodeWiki supports multiple LLM providers through `config/llm_providers.json`:

### Default Configuration (Privacy-First)

- **Ollama** (Priority 1, Enabled): 100% local, no API key needed
- **LM Studio** (Priority 2, Enabled): 100% local, OpenAI-compatible
- **Cloud Providers** (Priority 99, Disabled): OpenAI, Anthropic, Groq

Your code **never leaves your machine** unless you explicitly enable cloud providers.

### Adding Cloud Providers

1. Edit `config/llm_providers.json`
2. Find the provider (e.g., `openai`)
3. Set `enabled: true` and configure `api_key`
4. Optionally set environment variable:

```bash
export OPENAI_API_KEY="sk-proj-..."
codewiki --mode lifecycle
```

### Custom Endpoints

CodeWiki supports **any OpenAI-compatible API**:

```json
{
  "provider": "my_custom_llm",
  "api_type": "openai",
  "base_url": "http://localhost:8000/v1",
  "api_key": "${CUSTOM_API_KEY}",
  "models": ["your-model"],
  "priority": 1,
  "enabled": true
}
```

See [Multi-Provider Architecture](docs/MULTI_PROVIDER_ARCHITECTURE.md) for details.

## Configuration

### Local LLM Optimization

CodeWiki uses [LIR (Local Inference Runtime)](https://github.com/openjay/lir) for optimized local inference:

- **Automatic batching and scheduling** for improved throughput
- **Thermal-aware throttling** to reduce fan noise
- **Connection pooling** for faster requests
- **Multi-provider support** with intelligent failover

**Installation:**
```bash
# Install LIR as editable dependency (development)
pip install -e ../lir

# Or install from GitHub (production)
pip install git+https://github.com/openjay/lir.git@v0.1.0
```

**Performance:** 2.85x throughput improvement, 8.9x better latency

See [LIR Integration Guide](docs/LIR_INTEGRATION_GUIDE.md) for detailed setup.

### LLM Providers

CodeWiki supports **6+ LLM providers** with automatic failover:

#### Local Providers (Default, Free, Private)
1. **Ollama** (Primary): More accurate (85% parse success)
   ```bash
   ollama serve
   ollama pull qwen3:8b
   ```

2. **LM Studio** (Backup): Faster (~10x speed)
   - Start LM Studio GUI
   - Load any chat model
   - Automatic failover if Ollama unavailable

#### Cloud Providers (Optional, Disabled by Default)
- **OpenAI** (gpt-4, gpt-3.5-turbo)
- **Anthropic** (claude-3-opus, claude-3-sonnet)
- **Groq** (mixtral-8x7b, llama2-70b)
- **Custom** (any OpenAI-compatible endpoint)

All cloud providers are **disabled by default** for privacy.

Enable via `config/llm_providers.json` (see Multi-Provider Configuration section).

### Configuration Files

- `config/code_wiki_config.yaml`: Main configuration
- `config/llm_providers.json`: LLM provider settings

### Environment Variables

Override default configs:
```bash
export CODEWIKI_CONFIG=/path/to/custom/config.yaml
export CODEWIKI_LLM_PROVIDERS=/path/to/custom/providers.json
export CODEWIKI_LIR_POLICY=balanced  # silent/balanced/performance
```

## Usage Examples

### Scan Repository
```bash
codewiki --mode scan
```

### Lifecycle Classification (Rule-Based)
```bash
codewiki --mode lifecycle
```

### Lifecycle Classification (LLM-Enhanced)
```bash
# 1. Edit config/code_wiki_config.yaml: use_llm: true
# 2. Run classification
codewiki --mode lifecycle
```

### Preview Mode (Dry Run)
```bash
codewiki --mode lifecycle --preview
```

### Generate Documentation
```bash
codewiki --mode docs
```

### Inspect Results
```bash
python -m codewiki.inspect_lifecycle_result
python -m codewiki.inspect_lifecycle_result --verbose
```

## Safety Features

### Conservative Design
- **Multi-tier confidence thresholds**: Only allow archive/delete with confidence ≥ 0.6
- **Graceful fallback**: Automatic fallback to rule-based on LLM failures
- **No auto-deletion**: All destructive actions require human review
- **Clear-case detection**: 75% of files handled by safe rules, no LLM needed

### Expected Results
- **Parse success**: 85%+ (Ollama), 78%+ (LM Studio)
- **Review recommendations**: <50 files typical
- **False positives**: Near zero (validated on 664-file codebase)

## Architecture

```
┌─────────────────┐
│  CLI / Module   │
└────────┬────────┘
         │
┌────────▼────────┐     ┌──────────────┐
│  Orchestrator   │────▶│ Repo Scanner │
└────────┬────────┘     └──────────────┘
         │
         ├─────▶ Lifecycle Classifier
         │       ├─ Rule-based (fast)
         │       └─ LLM-enhanced (hybrid)
         │             │
         │             ▼
         │       ┌─────────────────┐
         │       │ Multi-Provider  │
         │       │   LLM Client    │
         │       │  ┌────────────┐ │
         │       │  │ Ollama     │ │
         │       │  │ LM Studio  │ │
         │       │  │ OpenAI     │ │
         │       │  │ Custom...  │ │
         │       │  └────────────┘ │
         │       └─────────────────┘
         │
         └─────▶ Doc Generator
                 └─ Markdown output
```

## Documentation

- [Multi-Provider Architecture](docs/MULTI_PROVIDER_ARCHITECTURE.md) - Flexible LLM provider system
- [LIR Integration Guide](docs/LIR_INTEGRATION_GUIDE.md) - Local inference optimization setup
- [LLM Integration Guide](docs/CODE_WIKI_LLM_INTEGRATION_GUIDE.md) - LLM provider configuration
- [Reasoning Model Fix](docs/REASONING_MODEL_FIX.md) - Support for reasoning models
- [Operational Guide](docs/CODE_WIKI_OPERATIONAL_GUIDE.md) - Daily usage and best practices
- [Design Document](docs/CODE_WIKI_DESIGN.md) - Architecture and design decisions

## Performance

Tested on 664-file Python codebase:

| Mode | Runtime | LLM Calls | Parse Success | Review Count |
|------|---------|-----------|---------------|--------------|
| Rule-based | 0.1s | 0 | N/A | 0 |
| LLM Full | ~7 min | 664 | 78% | 426 |
| **LLM Hybrid** | **~2-3 min** | **150** | **85%** | **6** |

**Key Achievement**: 77% fewer LLM calls, 99% fewer review recommendations vs full mode.

## Requirements

- Python ≥ 3.10
- `pyyaml >= 6.0`
- `requests >= 2.28`
- Local LLM (Ollama or LM Studio) - optional

## Development

```bash
# Clone repository
git clone https://github.com/openjay/codewiki.git
cd codewiki

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Format code
black codewiki/
ruff check codewiki/
```

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Related Projects

- [Digital Me](https://github.com/openjay/longter) - Autonomous multi-agent AI platform (where CodeWiki was originally developed)

## Version

**Current**: 2.1.0 (Multi-Provider Architecture)

### Changelog

- **v2.1.0** (2025-12-30)
  - Multi-provider architecture (6+ providers)
  - OpenAI-compatible API support
  - Automatic API type detection
  - Reasoning model support (`<think>` tag parsing)
  - Flexible authentication (environment variables)
  - Privacy-first defaults maintained
  
- **v2.0.0** (2025-12-20)
  - LIR-powered local inference optimization (2.85x speedup)
  - Thermal-aware throttling
  - Connection pooling
  
- **v1.2.0** (2025-11-20)
  - Hybrid mode implementation
  - LLM integration
  
- **v1.0.0** (2025-11-15)
  - Initial release
  - Rule-based classification
  - Documentation generation

## Author

Jay - 2025

