"""
Tests for multi-provider LLM client architecture.

Validates:
- Loading providers from config (all types, not just ollama/lm_studio)
- API type detection (explicit and auto-detect)
- Authentication (API keys and env var expansion)
- Priority-based provider selection
- Failover between different API types
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codewiki.llm_client import LocalLLMClient, ProviderConfig


class TestProviderConfig:
    """Test ProviderConfig dataclass"""

    def test_provider_config_with_api_type(self):
        """Test creating ProviderConfig with api_type"""
        config = ProviderConfig(
            provider="openai",
            base_url="https://api.openai.com",
            api_type="openai",
            api_key="sk-test",
            priority=1,
        )
        assert config.api_type == "openai"
        assert config.api_key == "sk-test"

    def test_provider_config_without_api_type(self):
        """Test creating ProviderConfig without api_type (auto-detect)"""
        config = ProviderConfig(
            provider="ollama",
            base_url="http://localhost:11434",
            priority=1,
        )
        assert config.api_type is None  # Will be auto-detected


class TestProviderLoading:
    """Test loading providers from config"""

    def test_load_all_provider_types(self):
        """Test that all provider types are loaded (not just ollama/lm_studio)"""
        config_data = {
            "providers": [
                {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "models": ["qwen3:8b"],
                    "priority": 1,
                    "enabled": True,
                },
                {
                    "provider": "openai",
                    "base_url": "https://api.openai.com",
                    "api_key": "${OPENAI_API_KEY}",
                    "models": ["gpt-4"],
                    "priority": 2,
                    "enabled": True,
                },
                {
                    "provider": "custom_cloud",
                    "base_url": "http://localhost:8317/v1",
                    "api_key": "sk-test",
                    "models": ["gpt-5.2"],
                    "priority": 3,
                    "enabled": True,
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            client = LocalLLMClient(config_path=config_path)
            
            # Should load all 3 providers
            assert len(client.providers) == 3
            
            # Check provider names
            provider_names = [p.provider for p in client.providers]
            assert "ollama" in provider_names
            assert "openai" in provider_names
            assert "custom_cloud" in provider_names
            
        finally:
            config_path.unlink()

    def test_load_providers_with_api_type(self):
        """Test loading providers with explicit api_type field"""
        config_data = {
            "providers": [
                {
                    "provider": "custom",
                    "api_type": "openai",
                    "base_url": "http://custom.local",
                    "models": ["custom-model"],
                    "priority": 1,
                    "enabled": True,
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            client = LocalLLMClient(config_path=config_path)
            assert len(client.providers) == 1
            assert client.providers[0].api_type == "openai"
        finally:
            config_path.unlink()


class TestAPITypeDetection:
    """Test API type detection logic"""

    def test_explicit_api_type(self):
        """Test that explicit api_type is used"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="custom",
            base_url="http://test",
            api_type="ollama",
        )
        
        assert client._detect_api_type(provider) == "ollama"

    def test_detect_ollama_by_name(self):
        """Test auto-detection of Ollama by provider name"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="ollama",
            base_url="http://localhost:11434",
        )
        
        assert client._detect_api_type(provider) == "ollama"

    def test_detect_openai_by_name(self):
        """Test auto-detection of OpenAI-compatible by provider name"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        test_cases = [
            "lm_studio",
            "openai",
            "anthropic",
            "groq",
            "together",
        ]
        
        for provider_name in test_cases:
            provider = ProviderConfig(
                provider=provider_name,
                base_url="http://test",
            )
            assert client._detect_api_type(provider) == "openai", \
                f"Failed for provider: {provider_name}"

    def test_default_to_openai(self):
        """Test that unknown providers default to OpenAI format"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="unknown_custom_provider",
            base_url="http://test",
        )
        
        # Should default to openai (more common)
        assert client._detect_api_type(provider) == "openai"


class TestAuthentication:
    """Test API key resolution and authentication"""

    def test_resolve_direct_api_key(self):
        """Test resolving direct API key"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="openai",
            base_url="http://test",
            api_key="sk-direct-key-123",
        )
        
        assert client._resolve_api_key(provider) == "sk-direct-key-123"

    def test_resolve_env_var_api_key(self):
        """Test resolving API key from environment variable"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="openai",
            base_url="http://test",
            api_key="${TEST_API_KEY}",
        )
        
        with patch.dict(os.environ, {"TEST_API_KEY": "sk-from-env"}):
            assert client._resolve_api_key(provider) == "sk-from-env"

    def test_resolve_missing_env_var(self):
        """Test handling of missing environment variable"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="openai",
            base_url="http://test",
            api_key="${MISSING_VAR}",
        )
        
        # Should return None and log warning
        assert client._resolve_api_key(provider) is None

    def test_no_api_key(self):
        """Test provider without API key"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        
        provider = ProviderConfig(
            provider="ollama",
            base_url="http://localhost:11434",
        )
        
        assert client._resolve_api_key(provider) is None


class TestPrioritySelection:
    """Test priority-based provider selection"""

    def test_select_by_priority(self):
        """Test that providers are selected by priority (lower number = higher priority)"""
        config_data = {
            "providers": [
                {
                    "provider": "low_priority",
                    "base_url": "http://low",
                    "models": ["model"],
                    "priority": 10,
                    "enabled": True,
                },
                {
                    "provider": "high_priority",
                    "base_url": "http://high",
                    "models": ["model"],
                    "priority": 1,
                    "enabled": True,
                },
                {
                    "provider": "medium_priority",
                    "base_url": "http://medium",
                    "models": ["model"],
                    "priority": 5,
                    "enabled": True,
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.object(LocalLLMClient, "_check_provider_health", return_value=True):
                client = LocalLLMClient(config_path=config_path)
                
                # Should select high_priority (priority=1)
                assert client.active is not None
                assert client.active.provider == "high_priority"
        finally:
            config_path.unlink()

    def test_skip_disabled_providers(self):
        """Test that disabled providers are skipped"""
        config_data = {
            "providers": [
                {
                    "provider": "disabled",
                    "base_url": "http://disabled",
                    "models": ["model"],
                    "priority": 1,
                    "enabled": False,
                },
                {
                    "provider": "enabled",
                    "base_url": "http://enabled",
                    "models": ["model"],
                    "priority": 2,
                    "enabled": True,
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with patch.object(LocalLLMClient, "_check_provider_health", return_value=True):
                client = LocalLLMClient(config_path=config_path)
                
                # Should select enabled provider (priority=2)
                assert client.active is not None
                assert client.active.provider == "enabled"
        finally:
            config_path.unlink()


class TestGenerateRouting:
    """Test generate() routing based on API type"""

    def test_route_to_ollama(self):
        """Test that Ollama providers route to _generate_ollama()"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        client.active = ProviderConfig(
            provider="ollama",
            base_url="http://localhost:11434",
            api_type="ollama",
            model="qwen3:8b",
        )
        
        with patch.object(client, "_generate_ollama", return_value="ollama response") as mock:
            result = client.generate("test prompt")
            assert result == "ollama response"
            mock.assert_called_once()

    def test_route_to_openai(self):
        """Test that OpenAI-compatible providers route to _generate_openai()"""
        client = LocalLLMClient(config_path=Path("nonexistent.json"))
        client.active = ProviderConfig(
            provider="openai",
            base_url="https://api.openai.com",
            api_type="openai",
            model="gpt-4",
        )
        
        with patch.object(client, "_generate_openai", return_value="openai response") as mock:
            result = client.generate("test prompt")
            assert result == "openai response"
            mock.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

