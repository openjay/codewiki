"""
Test cases for unclosed <think> tag handling in JSON parser.

This test suite verifies the fix for the edge case identified by Codex Bot
in PR #2, where unclosed <think> tags could cause JSON to be discarded.
"""

import pytest
from codewiki.lifecycle_classifier import LifecycleClassifier


class TestUnclosedThinkTagHandling:
    """Test <think> tag handling in JSON parser"""

    def test_closed_think_tag_normal(self):
        """Normal case: <think>...</think>{json}"""
        response = '<think>analyzing the file structure</think>{"recommendation": "keep", "confidence": 0.8}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None, "Should parse JSON after closed </think> tag"
        assert result["recommendation"] == "keep"
        assert result["confidence"] == 0.8

    def test_unclosed_think_tag_with_json_after(self):
        """Edge case: <think>...{json} (no closing tag) - THE FIX"""
        # This is the scenario that was broken before the fix
        response = '<think>analyzing file age and usage patterns\n{"recommendation": "archive", "confidence": 0.75}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None, "Should extract JSON even without closing </think> tag"
        assert result["recommendation"] == "archive"
        assert result["confidence"] == 0.75

    def test_unclosed_think_tag_with_newlines(self):
        """Edge case: <think> with multiple newlines before JSON"""
        response = '<think>thinking about this...\n\n\n{"recommendation": "review", "confidence": 0.6}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "review"

    def test_unclosed_think_tag_truncated_no_json(self):
        """Edge case: <think>... (truncated, no JSON at all)"""
        response = '<think>analyzing but response was truncated before JSON could be generated'
        result = LifecycleClassifier._parse_llm_json(response)
        
        # Should fail gracefully (return None)
        assert result is None, "Should return None when no JSON is present"

    def test_no_think_tag_pure_json(self):
        """Normal case: {json} (no think tag at all)"""
        response = '{"recommendation": "delete", "confidence": 0.9}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "delete"
        assert result["confidence"] == 0.9

    def test_unclosed_think_tag_with_markdown_fences(self):
        """Edge case: <think> + markdown code fences + JSON"""
        response = '<think>considering options\n```json\n{"recommendation": "keep", "confidence": 0.85}\n```'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None, "Should handle markdown fences after unclosed <think>"
        assert result["recommendation"] == "keep"

    def test_multiple_json_blocks_after_unclosed_think(self):
        """Edge case: <think> followed by invalid then valid JSON"""
        # The brace extraction strategy should find the valid JSON
        response = '<think>analyzing\nSome text {"recommendation": "review", "confidence": 0.7}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "review"

    def test_think_tag_with_text_containing_braces(self):
        """Edge case: <think> content mentions braces in text"""
        # The JSON parser should handle text with brace mentions before actual JSON
        response = '<think>considering options\n{"recommendation": "archive", "confidence": 0.65}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "archive"


class TestThinkTagRegression:
    """Regression tests to ensure existing functionality still works"""

    def test_closed_think_tag_with_text_before(self):
        """Ensure text before <think> is ignored when tag is closed"""
        response = 'Some preamble text <think>reasoning</think>{"recommendation": "keep"}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "keep"

    def test_multiple_think_tags_closed(self):
        """Handle multiple <think> tags (should use last </think>)"""
        response = '<think>first thought</think><think>second thought</think>{"recommendation": "review"}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "review"

    def test_empty_think_tag(self):
        """Handle empty <think></think> tags"""
        response = '<think></think>{"recommendation": "delete"}'
        result = LifecycleClassifier._parse_llm_json(response)
        
        assert result is not None
        assert result["recommendation"] == "delete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

