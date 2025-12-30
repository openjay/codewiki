# Multi-Provider LLM Architecture

**Status:** ✅ Implemented (v2.0)  
**Date:** 2025-12-30

## Overview

CodeWiki now supports **any OpenAI-compatible LLM provider** through a flexible, configuration-driven architecture. This enables users to choose between local inference (100% private), cloud APIs (optional), or custom endpoints, all through simple JSON configuration.

## Key Features

### 1. Universal Provider Support
- **Local Providers**: Ollama, LM Studio (100% private, no API keys)
- **Cloud Providers**: OpenAI, Anthropic, Groq (opt-in, requires API keys)
- **Custom Endpoints**: Any OpenAI-compatible API

### 2. Automatic API Format Detection
- Detects Ollama vs OpenAI-compatible format automatically
- Supports explicit `api_type` override in config
- Heuristic-based detection using provider names

### 3. Flexible Authentication
- Direct API keys in config
- Environment variable expansion (`${OPENAI_API_KEY}`)
- No authentication for local providers

### 4. Priority-Based Failover
- Lower priority number = higher priority
- Automatic failover on provider failure
- Health checks before selection

### 5. Privacy-First Defaults
- Local providers enabled by default (priority 1-2)
- Cloud providers disabled by default (priority 99)
- Clear cost and privacy indicators in config

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CodeWiki Application                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   LocalLLMClient                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Provider Loader (config/llm_providers.json)          │  │
│  │ - Loads all enabled providers                        │  │
│  │ - No hardcoded type filtering                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ API Type Detector                                    │  │
│  │ - Explicit: Use api_type from config                │  │
│  │ - Heuristic: Detect by provider name                │  │
│  │ - Default: OpenAI format (most common)              │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Authentication Handler                               │  │
│  │ - Resolve API keys                                   │  │
│  │ - Expand environment variables                       │  │
│  │ - Add Authorization headers                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Generate Router                                      │  │
│  │ ┌─────────────────┐    ┌──────────────────────────┐ │  │
│  │ │ Ollama Adapter  │    │ OpenAI Adapter           │ │  │
│  │ │ /api/generate   │    │ /v1/chat/completions     │ │  │
│  │ └─────────────────┘    └──────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM Providers                             │
│  ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌────────────┐ │
│  │ Ollama   │  │ LM Studio │  │ OpenAI  │  │ Custom API │ │
│  │ (Local)  │  │ (Local)   │  │ (Cloud) │  │ (Cloud)    │ │
│  └──────────┘  └───────────┘  └─────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow

1. **Configuration Load**: Read `config/llm_providers.json`
2. **Provider Selection**: Sort by priority, filter by enabled status
3. **Health Check**: Verify provider availability
4. **API Type Detection**: Determine Ollama vs OpenAI format
5. **Authentication**: Resolve API keys, add headers
6. **Request Routing**: Call appropriate adapter (_generate_ollama or _generate_openai)
7. **Failover**: On failure, try next priority provider

## Implementation Details

### Files Modified

1. **`codewiki/llm_client.py`** (Core changes)
   - Updated `ProviderConfig` dataclass with `api_type` and `api_key` fields
   - Removed hardcoded provider type filter
   - Added `_detect_api_type()` method
   - Added `_resolve_api_key()` method with env var expansion
   - Updated `_check_provider_health()` to support both API formats
   - Refactored `generate()` to route based on detected API type
   - Renamed `_generate_lm_studio()` → `_generate_openai()` with auth support

2. **`codewiki/llm_client_lir.py`** (LIR wrapper)
   - Updated `_load_providers_config()` to load all enabled providers
   - Maps top 2 providers to LIR's ollama/lmstudio slots for backward compatibility

3. **`config/llm_providers.json`** (Configuration)
   - Added `api_type` field to all providers
   - Added privacy and cost notes
   - Set local providers as priority 1-2 (enabled)
   - Set cloud providers as priority 99 (disabled by default)
   - Added `_readme` field with privacy notice

4. **`tests/test_multi_provider.py`** (New test suite)
   - 16 comprehensive tests covering all new functionality
   - Tests for provider loading, API detection, authentication, priority selection, routing

5. **`docs/CODE_WIKI_LLM_INTEGRATION_GUIDE.md`** (Documentation)
   - Added multi-provider architecture section
   - Added provider configuration guide
   - Added authentication examples
   - Added custom provider instructions

## Configuration Examples

### Example 1: Local-Only (Default)

```json
{
  "providers": [
    {
      "provider": "ollama",
      "api_type": "ollama",
      "base_url": "http://localhost:11434",
      "models": ["qwen3:8b"],
      "priority": 1,
      "enabled": true
    },
    {
      "provider": "lm_studio",
      "api_type": "openai",
      "base_url": "http://localhost:1234",
      "models": ["local-model"],
      "priority": 2,
      "enabled": true
    }
  ]
}
```

**Result**: 100% local inference, no data leaves machine, no API keys needed.

### Example 2: Local Primary, Cloud Backup

```json
{
  "providers": [
    {
      "provider": "ollama",
      "base_url": "http://localhost:11434",
      "models": ["qwen3:8b"],
      "priority": 1,
      "enabled": true
    },
    {
      "provider": "openai",
      "api_type": "openai",
      "base_url": "https://api.openai.com",
      "api_key": "${OPENAI_API_KEY}",
      "models": ["gpt-3.5-turbo"],
      "priority": 2,
      "enabled": true
    }
  ]
}
```

**Result**: Uses local Ollama first, falls back to OpenAI if Ollama is unavailable.

### Example 3: Custom Cloud Endpoint

```json
{
  "providers": [
    {
      "provider": "my_custom_llm",
      "api_type": "openai",
      "base_url": "http://localhost:8317/v1",
      "api_key": "sk-custom-key-123",
      "models": ["gpt-5.2"],
      "priority": 1,
      "enabled": true
    }
  ]
}
```

**Result**: Uses custom OpenAI-compatible endpoint as primary provider.

## Testing

### Unit Tests

All tests pass (16 new tests + 41 existing tests = 57 total):

```bash
pytest tests/test_multi_provider.py -v
# 16 passed

pytest tests/ -v
# 57 passed, 4 warnings
```

### Integration Tests

Manual integration testing confirmed:

1. ✅ LocalLLMClient loads all provider types
2. ✅ API type detection works (explicit and auto-detect)
3. ✅ Authentication with API keys and env vars
4. ✅ Priority-based provider selection
5. ✅ Failover between providers
6. ✅ CodeWiki lifecycle classification with multi-provider
7. ✅ LIR wrapper compatibility

## Migration Guide

### For Existing Users

**No changes required!** Existing configurations continue to work:

- Old configs with `ollama` and `lm_studio` providers work unchanged
- Default behavior remains local-only
- No breaking changes to API

### To Add Cloud Providers

1. Edit `config/llm_providers.json`
2. Add new provider entry with `api_key`
3. Set `enabled: true` and appropriate `priority`
4. Set environment variable if using `${ENV_VAR}` syntax

```bash
export OPENAI_API_KEY="sk-proj-..."
python -m codewiki.orchestrator --mode lifecycle
```

## Benefits

### For Open Source Community

1. **Zero Vendor Lock-in**: Use any provider, switch anytime
2. **Privacy-First**: Local by default, cloud opt-in
3. **Cost Control**: Free local options, clear cost indicators
4. **Extensibility**: Add new providers via config, no code changes
5. **Transparency**: All provider details visible in config
6. **Compliance-Friendly**: GDPR/HIPAA compatible with local-only mode

### For Developers

1. **Simplified Codebase**: No hardcoded provider logic
2. **Testability**: Easy to mock providers in tests
3. **Maintainability**: Provider changes don't require code updates
4. **Flexibility**: Support new providers immediately via config

### For Users

1. **Choice**: Pick the best provider for their needs
2. **Reliability**: Automatic failover ensures uptime
3. **Performance**: Can use fastest available provider
4. **Security**: Control where data goes (local vs cloud)

## Future Enhancements

### Phase 3: LIR Package Enhancement (Planned)

Currently, LIR wrapper maps providers to fixed slots. Future enhancement:

1. Create `OpenAIGenericProvider` in LIR package
2. Update `LIRClient.__init__()` to accept custom provider list
3. Enable LIR to use any provider dynamically

This will enable full LIR optimization (batching, thermal management) for all providers, not just the top 2.

### Additional Potential Features

- Provider-specific retry strategies
- Cost tracking and budgets
- Response caching
- A/B testing between providers
- Provider performance metrics

## Conclusion

The multi-provider architecture successfully transforms CodeWiki from a hardcoded, local-only system to a flexible, configuration-driven platform that supports any LLM provider while maintaining privacy-first defaults and zero breaking changes for existing users.

**Key Achievement**: Open-source friendly architecture that gives users complete control over their LLM infrastructure without sacrificing ease of use or privacy.

