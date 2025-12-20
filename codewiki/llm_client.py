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


class LocalLLMClient:
    """
    Multi-provider local LLM client with priority + failover.

    Supports: Ollama / LM Studio
    - Reads from config/llm_providers.json
    - Auto-selects priority-based available provider
    - Fallback chain: Ollama → LM Studio → None

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

        Unified interface that routes to:
        - Ollama → _generate_ollama()
        - LM Studio → _generate_lm_studio()

        Args:
            prompt: User prompt
            system_prompt: Optional system context

        Returns:
            Generated text or None if all providers fail
        """
        if not self.active:
            return None

        if self.active.provider == "ollama":
            return self._generate_ollama(prompt, system_prompt)
        elif self.active.provider == "lm_studio":
            return self._generate_lm_studio(prompt, system_prompt)
        else:
            logger.error(f"Unsupported provider: {self.active.provider}")
            return None

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

                # Only load local providers (skip OpenAI, Anthropic, etc.)
                if provider_name not in ["ollama", "lm_studio"]:
                    continue

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

            if provider.provider == "ollama":
                # Ollama health check: GET /api/tags
                resp = requests.get(f"{base_url}/api/tags", timeout=3)
                return resp.status_code == 200

            elif provider.provider == "lm_studio":
                # LM Studio health check: GET /v1/models (OpenAI compatible)
                resp = requests.get(f"{base_url}/v1/models", timeout=3)
                return resp.status_code == 200

            else:
                return False

        except Exception:
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

    def _generate_lm_studio(
        self, prompt: str, system_prompt: Optional[str]
    ) -> Optional[str]:
        """
        Generate text using LM Studio API (OpenAI-compatible).

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text or None if error
        """
        try:
            base_url = self.active.base_url.rstrip("/")
            url = f"{base_url}/v1/chat/completions"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload: Dict[str, Any] = {
                "model": self.active.model or "qwen3:8b",
                "messages": messages,
                "temperature": 0.1,  # Temperature controlled in code, not config (source of truth)
                "max_tokens": 1000,  # Sufficient for instruct models; use 2500+ for reasoning models
            }

            resp = requests.post(url, json=payload, timeout=60)

            if resp.status_code != 200:
                logger.error(f"LM Studio error {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            self._update_usage(prompt, text)
            return text

        except Exception as e:
            logger.error(f"LM Studio generate error: {e}")
            return None

    def _update_usage(self, prompt: str, text: str) -> None:
        """Update usage statistics after successful generation"""
        self._request_count += 1
        # Estimate tokens: ~1 token per 4 characters (rough approximation)
        tokens = (len(prompt) + len(text)) // 4
        self._total_tokens += tokens
