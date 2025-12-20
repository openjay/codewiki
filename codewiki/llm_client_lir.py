"""
LIR Adapter for CodeWiki Lifecycle Classifier

Provides a sync wrapper around LIR that matches the existing
LocalLLMClient interface, enabling drop-in replacement.

Usage:
    # In lifecycle_classifier.py
    from .llm_client_lir import LIRLocalLLMClient
    
    client = LIRLocalLLMClient(policy="balanced")
    result = client.generate("Analyze this file...", system_prompt="...")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import LIR (now installed as separate package)
try:
    from lir import SyncLIRClient
    HAS_LIR = True
except ImportError as e:
    HAS_LIR = False
    logger.warning("LIR not available: %s. Install with: pip install -e ../lir", e)


class LIRLocalLLMClient:
    """
    LIR-based LLM client compatible with existing LocalLLMClient interface.
    
    Provides the same API as LocalLLMClient:
    - is_available() -> bool
    - generate(prompt, system_prompt) -> Optional[str]
    - get_usage_stats() -> Dict[str, Any]
    
    But uses LIR for:
    - Automatic batching
    - Concurrent request handling
    - Thermal-aware throttling
    - Multi-provider failover
    """
    
    def __init__(
        self,
        policy: str = "balanced",
        config_path: Optional[Path] = None,
        ollama_url: str = "http://localhost:11434",
        lmstudio_url: str = "http://localhost:1234",
        ollama_model: str = "qwen3:8b",
        lmstudio_model: str = "local-model",
    ):
        """
        Initialize LIR-based LLM client.
        
        Args:
            policy: LIR policy ("silent", "balanced", "performance")
            config_path: Optional path to LIR config
            ollama_url: Ollama server URL
            lmstudio_url: LM Studio server URL
            ollama_model: Ollama model name
            lmstudio_model: LM Studio model name
        """
        self.policy = policy
        self._client: Optional[SyncLIRClient] = None
        self._config = {
            "ollama_url": ollama_url,
            "lmstudio_url": lmstudio_url,
            "ollama_model": ollama_model,
            "lmstudio_model": lmstudio_model,
            "config_path": config_path,
        }
        
        # Track usage stats
        self._request_count = 0
        self._total_tokens = 0
        
        # Initialize client
        self._init_client()
    
    def _init_client(self) -> None:
        """Initialize LIR client"""
        if not HAS_LIR:
            logger.warning("LIR not available, client will not work")
            return
        
        try:
            self._client = SyncLIRClient(
                policy=self.policy,
                config_path=self._config.get("config_path"),
                ollama_url=self._config["ollama_url"],
                lmstudio_url=self._config["lmstudio_url"],
                ollama_model=self._config["ollama_model"],
                lmstudio_model=self._config["lmstudio_model"],
            )
            logger.info("LIR client initialized (policy=%s)", self.policy)
        except Exception as e:
            logger.error("Failed to initialize LIR client: %s", e)
            self._client = None
    
    def is_available(self) -> bool:
        """
        Check if LIR client is available and has healthy providers.
        
        Returns:
            True if at least one provider is accessible
        """
        if not HAS_LIR or self._client is None:
            return False
        
        try:
            return self._client.is_available()
        except Exception as e:
            logger.warning("LIR availability check failed: %s", e)
            return False
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> Optional[str]:
        """
        Generate text using LIR.
        
        Compatible with LocalLLMClient.generate() interface.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system context
            temperature: Sampling temperature (default: 0.1)
            max_tokens: Maximum tokens to generate (default: 1000, sufficient for instruct models; use 2500+ for reasoning models)
            
        Returns:
            Generated text or None if failed
        """
        if not HAS_LIR or self._client is None:
            logger.warning("LIR not available, returning None")
            return None
        
        try:
            result = self._client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            if result:
                self._request_count += 1
                # Estimate tokens (rough approximation)
                self._total_tokens += (len(prompt) + len(result)) // 4
            
            return result
            
        except Exception as e:
            logger.error("LIR generation failed: %s", e)
            return None
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Compatible with LocalLLMClient.get_usage_stats() interface.
        
        Returns:
            Dict with usage stats
        """
        stats = {
            "total_requests": self._request_count,
            "estimated_total_tokens": self._total_tokens,
            "cost": 0.0,  # Always free for local models
            "backend": "lir",
            "policy": self.policy,
        }
        
        # Add LIR metrics if available
        if self._client:
            try:
                lir_metrics = self._client.get_metrics()
                stats["lir_metrics"] = lir_metrics
                
                # Extract active provider info
                router_metrics = lir_metrics.get("router", {})
                stats["provider"] = router_metrics.get("active_provider")
                
            except Exception as e:
                logger.warning("Failed to get LIR metrics: %s", e)
        
        return stats
    
    def set_policy(self, policy: str) -> None:
        """
        Change LIR policy at runtime.
        
        Args:
            policy: New policy name ("silent", "balanced", "performance")
        """
        if self._client:
            self._client.set_policy(policy)
            self.policy = policy
            logger.info("LIR policy changed to: %s", policy)
    
    def close(self) -> None:
        """Close LIR client and cleanup resources"""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning("Error closing LIR client: %s", e)
            self._client = None
    
    def __enter__(self) -> "LIRLocalLLMClient":
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()


def create_llm_client(
    use_lir: bool = True,
    policy: str = "balanced",
    **kwargs,
):
    """
    Factory function to create appropriate LLM client.
    
    Args:
        use_lir: If True, use LIR client; if False, use legacy LocalLLMClient
        policy: LIR policy (only used if use_lir=True)
        **kwargs: Additional arguments for client initialization
        
    Returns:
        LLM client instance (LIRLocalLLMClient or LocalLLMClient)
    """
    if use_lir and HAS_LIR:
        try:
            client = LIRLocalLLMClient(policy=policy, **kwargs)
            if client.is_available():
                logger.info("Using LIR client (policy=%s)", policy)
                return client
            else:
                logger.warning("LIR not available, falling back to legacy client")
        except Exception as e:
            logger.warning("Failed to create LIR client: %s, falling back", e)
    
    # Fallback to legacy client
    from .llm_client import LocalLLMClient
    logger.info("Using legacy LocalLLMClient")
    return LocalLLMClient(**kwargs)

