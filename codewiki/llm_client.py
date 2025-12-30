"""
LLM Client for Code Wiki

Multi-provider local LLM integration with automatic fallback.
Supports Ollama (priority 1) and LM Studio (priority 2) for redundancy.

Design (following architect guidance):
- Minimal interface: is_available(), generate(), get_usage_stats()
- Priority-based provider selection with automatic failover
- Loads config from config/llm_providers.json
- Synchronous API (no async complexity for V1.1)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider"""

    provider: str
    base_url: str
    priority: int = 1
    enabled: bool = True
    model: Optional[str] = None
    api_type: Optional[str] = None  # 'ollama', 'openai', or None (auto-detect)
    api_key: Optional[str] = None  # API key or ${ENV_VAR} for expansion


class LocalLLMClient:
    """
    Multi-provider LLM client with priority-based failover.

    Supports: Any OpenAI-compatible API (Ollama, LM Studio, OpenAI, Anthropic, custom endpoints)
    - Reads from config/llm_providers.json
    - Auto-detects API format (Ollama vs OpenAI-compatible)
    - Auto-selects priority-based available provider
    - Supports both local and cloud providers with authentication

    Minimal Interface:
    - is_available() -> bool
    - generate(prompt, system_prompt) -> Optional[str]
    - get_usage_stats() -> Dict[str, Any]
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize multi-provider LLM client.

        Args:
            config_path: Path to llm_providers.json.
                        If None, defaults to config/llm_providers.json
        """
        self.config_path = config_path or Path("config/llm_providers.json")
        self.providers: List[ProviderConfig] = []
        self.active: Optional[ProviderConfig] = None
        self._total_tokens = 0
        self._request_count = 0

        self._load_providers()
        self._select_active_provider()

    # --------- Public API (Code Wiki uses these 3 methods) ---------

    def is_available(self) -> bool:
        """Check if any LLM provider is available"""
        return self.active is not None

    def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate text using the active provider.

        Automatically detects API format and routes to appropriate implementation:
        - Ollama format → _generate_ollama()
        - OpenAI-compatible format → _generate_openai()

        Args:
            prompt: User prompt
            system_prompt: Optional system context

        Returns:
            Generated text or None if generation fails
        """
        if not self.active:
            return None

        # Detect and cache API type for this provider
        if not hasattr(self.active, '_detected_api_type'):
            self.active._detected_api_type = self._detect_api_type(self.active)

        if self.active._detected_api_type == "ollama":
            return self._generate_ollama(prompt, system_prompt)
        else:  # openai format
            return self._generate_openai(prompt, system_prompt)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics across all requests"""
        return {
            "total_requests": self._request_count,
            "estimated_total_tokens": self._total_tokens,
            "cost": 0.0,  # Always free for local models
            "provider": self.active.provider if self.active else None,
            "base_url": self.active.base_url if self.active else None,
            "model": self.active.model if self.active else None,
        }

    # --------- Internal: Load config & select provider ---------

    def _load_providers(self) -> None:
        """
        Load provider configurations from config/llm_providers.json

        Supports two formats:
        1. List: [{"provider": "ollama", ...}, ...]
        2. Dict: {"providers": [{"provider": "ollama", ...}, ...]}
        """
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))

            # Handle both formats
            if isinstance(data, dict) and "providers" in data:
                items = data["providers"]
            else:
                items = data

            for item in items:
                provider_name = item.get("provider")
                if not provider_name:
                    continue

                # Load all enabled providers (no filtering by type)
                self.providers.append(
                    ProviderConfig(
                        provider=item["provider"],
                        base_url=item["base_url"],
                        priority=int(item.get("priority", 1)),
                        enabled=bool(item.get("enabled", True)),
                        model=item.get("model")
                        or (
                            item.get("models", [None])[0]
                            if isinstance(item.get("models"), list)
                            else None
                        ),
                        api_type=item.get("api_type"),
                        api_key=item.get("api_key"),
                    )
                )

        except Exception as e:
            logger.error(f"Failed to load LLM providers from {self.config_path}: {e}")
            self.providers = []

    def _select_active_provider(self) -> None:
        """
        Select active provider based on priority and availability.

        Strategy:
        1. Sort by priority (lower number = higher priority)
        2. Try each enabled provider
        3. First healthy provider becomes active
        4. If none available, active remains None
        """
        # Sort by priority, lowest number first
        candidates = sorted(
            [p for p in self.providers if p.enabled],
            key=lambda p: p.priority,
        )

        for provider in candidates:
            if self._check_provider_health(provider):
                self.active = provider
                logger.info(
                    f"[LocalLLM] Active provider: {provider.provider} "
                    f"({provider.base_url}, model={provider.model})"
                )
                return

        logger.warning("[LocalLLM] No available LLM providers found")
        self.active = None

    def _resolve_api_key(self, provider: ProviderConfig) -> Optional[str]:
        """
        Resolve API key from config or environment variable.
        
        Supports:
        - Direct key: "api_key": "sk-..."
        - Env var expansion: "api_key": "${OPENAI_API_KEY}"
        
        Args:
            provider: Provider configuration
            
        Returns:
            Resolved API key or None
        """
        if not provider.api_key:
            return None
        
        # Check for environment variable expansion
        if provider.api_key.startswith("${") and provider.api_key.endswith("}"):
            var_name = provider.api_key[2:-1]
            api_key = os.getenv(var_name)
            if not api_key:
                logger.warning(
                    f"Environment variable {var_name} not set for provider {provider.provider}"
                )
            return api_key
        
        # Direct API key
        return provider.api_key

    def _detect_api_type(self, provider: ProviderConfig) -> str:
        """
        Detect API format (Ollama vs OpenAI-compatible).
        
        Strategy:
        1. If api_type explicitly set in config, use it
        2. If provider name is 'ollama', assume Ollama format
        3. If provider name contains 'studio' or is known cloud provider, assume OpenAI format
        4. Otherwise, try OpenAI format first (more common), fallback to Ollama
        
        Args:
            provider: Provider configuration
            
        Returns:
            'ollama' or 'openai'
        """
        # Explicit api_type in config takes precedence
        if provider.api_type:
            return provider.api_type.lower()
        
        # Heuristic based on provider name
        provider_lower = provider.provider.lower()
        
        if provider_lower == "ollama":
            return "ollama"
        
        # Known OpenAI-compatible providers
        if any(name in provider_lower for name in ["studio", "openai", "anthropic", "groq", "together", "replicate"]):
            return "openai"
        
        # Default to OpenAI format (more common for cloud/custom endpoints)
        logger.info(
            f"Provider {provider.provider} API type not specified, defaulting to OpenAI-compatible format"
        )
        return "openai"

    def _check_provider_health(self, provider: ProviderConfig) -> bool:
        """
        Check if a specific provider is healthy and accessible.

        Args:
            provider: Provider configuration

        Returns:
            True if provider responds to health check
        """
        try:
            base_url = provider.base_url.rstrip("/")
            api_type = self._detect_api_type(provider)
            
            # Prepare headers for authentication
            headers = {}
            api_key = self._resolve_api_key(provider)
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            if api_type == "ollama":
                # Ollama health check: GET /api/tags
                resp = requests.get(f"{base_url}/api/tags", timeout=3, headers=headers)
                return resp.status_code == 200
            else:
                # OpenAI-compatible health check: GET /v1/models
                # Handle base_url that may or may not include /v1
                if base_url.endswith("/v1"):
                    health_url = f"{base_url}/models"
                else:
                    health_url = f"{base_url}/v1/models"
                resp = requests.get(health_url, timeout=3, headers=headers)
                return resp.status_code == 200

        except Exception as e:
            logger.debug(f"Health check failed for {provider.provider}: {e}")
            return False

    # --------- Provider-specific generate implementations ---------

    def _generate_ollama(
        self, prompt: str, system_prompt: Optional[str]
    ) -> Optional[str]:
        """
        Generate text using Ollama API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text or None if error
        """
        try:
            base_url = self.active.base_url.rstrip("/")

            payload: Dict[str, Any] = {
                "model": self.active.model or "qwen3:8b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Temperature controlled in code, not config (source of truth)
                    "num_predict": 500,  # Max tokens for JSON response
                },
            }

            if system_prompt:
                payload["system"] = system_prompt

            resp = requests.post(
                f"{base_url}/api/generate",
                json=payload,
                timeout=60,
            )

            if resp.status_code != 200:
                logger.error(f"Ollama error {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            text = data.get("response", "")
            self._update_usage(prompt, text)
            return text

        except Exception as e:
            logger.error(f"Ollama generate error: {e}")
            return None

    def _generate_openai(
        self, prompt: str, system_prompt: Optional[str]
    ) -> Optional[str]:
        """
        Generate text using OpenAI-compatible API.
        
        Supports: LM Studio, OpenAI, Anthropic, Groq, and any OpenAI-compatible endpoint.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text or None if error
        """
        try:
            base_url = self.active.base_url.rstrip("/")
            # Handle base_url that may or may not include /v1
            if base_url.endswith("/v1"):
                url = f"{base_url}/chat/completions"
            else:
                url = f"{base_url}/v1/chat/completions"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload: Dict[str, Any] = {
                "model": self.active.model or "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.1,  # Temperature controlled in code, not config (source of truth)
                "max_tokens": 1000,  # Sufficient for instruct models; use 2500+ for reasoning models
            }

            # Add authentication header if API key is configured
            headers = {}
            api_key = self._resolve_api_key(self.active)
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            resp = requests.post(url, json=payload, headers=headers, timeout=60)

            if resp.status_code != 200:
                logger.error(
                    f"{self.active.provider} error {resp.status_code}: {resp.text}"
                )
                return None

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            self._update_usage(prompt, text)
            return text

        except Exception as e:
            logger.error(f"{self.active.provider} generate error: {e}")
            return None

    def _update_usage(self, prompt: str, text: str) -> None:
        """Update usage statistics after successful generation"""
        self._request_count += 1
        # Estimate tokens: ~1 token per 4 characters (rough approximation)
        tokens = (len(prompt) + len(text)) // 4
        self._total_tokens += tokens
