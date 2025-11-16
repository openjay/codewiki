# CodeWiki

**LLM-enhanced code lifecycle analysis and documentation generator**

CodeWiki helps you maintain clean codebases by automatically analyzing files, classifying their lifecycle status, and generating up-to-date documentation.

## Features

- 🔍 **Repository Scanning**: Comprehensive codebase analysis with metadata extraction
- 🤖 **LLM-Enhanced Classification**: Uses local LLMs (Ollama + LM Studio) for intelligent file lifecycle analysis
- 🎯 **Hybrid Mode**: Smart selection of files for LLM analysis (77% fewer LLM calls vs full mode)
- 🛡️ **Conservative Safety**: Multi-tier confidence thresholds prevent accidental deletions
- 📊 **Automatic Documentation**: Generates markdown docs with architecture overviews
- 🔄 **Dual-Provider Support**: Ollama (accuracy) + LM Studio (speed) with automatic failover
- 📈 **Operational Profiles**: Daily/Weekly/Audit modes for different use cases

## Installation

```bash
# Install from source
git clone https://github.com/[username]/codewiki.git
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

## Configuration

### LLM Providers

CodeWiki supports dual-provider redundancy:

1. **Ollama** (Primary): More accurate (85% parse success)
   ```bash
   ollama serve
   # Ensure qwen3:8b is installed: ollama pull qwen3:8b
   ```

2. **LM Studio** (Backup): Faster (~10x speed)
   - Start LM Studio GUI
   - Load any chat model
   - Automatic failover if Ollama unavailable

### Configuration Files

- `config/code_wiki_config.yaml`: Main configuration
- `config/llm_providers.json`: LLM provider settings

### Environment Variables

Override default configs:
```bash
export CODEWIKI_CONFIG=/path/to/custom/config.yaml
export CODEWIKI_LLM_PROVIDERS=/path/to/custom/providers.json
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
         │
         └─────▶ Doc Generator
                 └─ Markdown output
```

## Documentation

- [Operational Guide](docs/CODE_WIKI_OPERATIONAL_GUIDE.md)
- [V1.2 Implementation Details](docs/CODE_WIKI_V1.2_HYBRID_COMPLETE.md)
- [Testing Guide](docs/CODE_WIKI_V1.2_TESTING_GUIDE.md)
- [Test Results](docs/CODE_WIKI_V1.2_TEST_RESULTS.md)

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
git clone https://github.com/[username]/codewiki.git
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

- [Digital Me](https://github.com/[username]/longter) - Autonomous multi-agent AI platform (where CodeWiki was originally developed)

## Version

**Current**: 1.2.0 (Hybrid Mode with dual-provider LLM support)

## Author

Jay - 2025

