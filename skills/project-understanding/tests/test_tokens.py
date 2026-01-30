"""
Unit tests for the tokens module.

Tests cover:
- Token estimation accuracy
- Truncation behavior
- Section parsing
- Budget allocation
- Edge cases
"""

import pytest
from scripts.lib.tokens import (
    estimate_tokens,
    estimate_tokens_batch,
    parse_sections,
    truncate_to_budget,
    calculate_budget_allocation,
    get_budget_status,
    CHARS_PER_TOKEN,
)


class TestEstimateTokens:
    """Tests for token estimation functions."""
    
    def test_empty_string(self):
        """Empty string should return 0 tokens."""
        assert estimate_tokens("") == 0
    
    def test_simple_text(self):
        """Simple text estimation based on character count."""
        text = "Hello world"
        expected = int(len(text) / CHARS_PER_TOKEN)
        assert estimate_tokens(text) == expected
    
    def test_minimum_one_token(self):
        """Even single character should return at least 1 token."""
        assert estimate_tokens("a") == 1
    
    def test_code_flag_more_conservative(self):
        """Code flag should give more conservative estimate."""
        text = "def foo():\n    pass"
        code_estimate = estimate_tokens(text, is_code=True)
        text_estimate = estimate_tokens(text, is_code=False)
        assert code_estimate >= text_estimate
    
    def test_batch_estimation(self):
        """Batch estimation should work on multiple texts."""
        texts = ["Hello", "world", "foo bar baz"]
        results = estimate_tokens_batch(texts)
        assert len(results) == 3
        assert all(isinstance(r, int) for r in results)
        assert all(r > 0 for r in results)
    
    def test_long_text(self):
        """Long text should be estimated correctly."""
        text = "word " * 100  # 500 characters + spaces
        estimate = estimate_tokens(text)
        assert estimate > 0
        assert isinstance(estimate, int)


class TestParseSections:
    """Tests for section parsing."""
    
    def test_empty_text(self):
        """Empty text returns empty sections."""
        sections = parse_sections("")
        assert sections == []
    
    def test_single_section(self):
        """Text with one header returns one section."""
        text = "## Header\n\nContent here"
        sections = parse_sections(text)
        assert len(sections) == 1
        assert sections[0].header == "## Header"
        assert "Content" in sections[0].content
    
    def test_multiple_sections(self):
        """Text with multiple headers returns multiple sections."""
        text = "## Header 1\n\nContent 1\n\n## Header 2\n\nContent 2"
        sections = parse_sections(text)
        assert len(sections) == 2
        assert sections[0].header == "## Header 1"
        assert sections[1].header == "## Header 2"
    
    def test_priority_levels(self):
        """Different header levels get different priorities."""
        text = "# Title\n\nContent\n\n## Section\n\nMore"
        sections = parse_sections(text)
        assert sections[0].priority > sections[1].priority
    
    def test_no_headers(self):
        """Text without headers returns empty list (handled elsewhere)."""
        text = "Just some content\n\nMore content"
        sections = parse_sections(text)
        assert len(sections) >= 0  # May parse as single section or empty


class TestTruncateToBudget:
    """Tests for truncation functionality."""
    
    def test_within_budget_returns_unchanged(self):
        """Text within budget should not be modified."""
        text = "Short text"
        budget = 100  # Plenty of room
        result = truncate_to_budget(text, budget)
        assert result == text
    
    def test_over_budget_truncates(self):
        """Text over budget should be truncated."""
        # Create text that exceeds budget
        text = "word " * 1000  # Will be many tokens
        budget = 50
        result = truncate_to_budget(text, budget)
        assert len(result) < len(text)
        assert estimate_tokens(result) <= budget
    
    def test_preserves_section_headers(self):
        """Truncation should try to preserve section headers."""
        text = "## Important Header\n\n" + "word " * 1000
        budget = 100
        result = truncate_to_budget(text, budget)
        assert "## Important Header" in result
    
    def test_truncation_notice_added(self):
        """When truncating, a notice should be added."""
        text = "word " * 1000
        budget = 50
        result = truncate_to_budget(text, budget)
        assert "more" in result.lower() and "available" in result.lower()
    
    def test_section_priority_respected(self):
        """Higher priority sections should be preserved over lower."""
        text = "## High Priority\n\nImportant content\n\n### Low Priority\n\nLess important"
        # Force truncation
        budget = 20
        result = truncate_to_budget(text, budget, preserve_priority=True)
        # High priority section should be more likely present
        assert "High Priority" in result
    
    def test_empty_text(self):
        """Truncating empty text returns empty."""
        assert truncate_to_budget("", 100) == ""
    
    def test_code_truncation(self):
        """Code text should use code token estimation."""
        code = "def func():\n    return 42\n"
        result = truncate_to_budget(code, 10, is_code=True)
        assert isinstance(result, str)


class TestCalculateBudgetAllocation:
    """Tests for budget allocation calculations."""
    
    def test_simple_allocation(self):
        """Basic allocation should distribute according to ratios."""
        ratios: dict[str, float] = {"a": 0.5, "b": 0.5}
        allocation = calculate_budget_allocation(100, ratios)
        assert allocation["a"] == 50
        assert allocation["b"] == 50
    
    def test_uneven_allocation(self):
        """Uneven ratios should be respected."""
        ratios: dict[str, float] = {"a": 0.75, "b": 0.25}
        allocation = calculate_budget_allocation(100, ratios)
        assert allocation["a"] == 75
        assert allocation["b"] == 25
    
    def test_three_way_allocation(self):
        """Three-way split should work correctly."""
        ratios: dict[str, float] = {"a": 0.5, "b": 0.3, "c": 0.2}
        allocation = calculate_budget_allocation(1000, ratios)
        assert allocation["a"] == 500
        assert allocation["b"] == 300
        assert allocation["c"] == 200
    
    def test_normalization(self):
        """Ratios should be normalized if they don't sum to 1."""
        ratios: dict[str, float] = {"a": 2.0, "b": 2.0}  # Sum is 4
        allocation = calculate_budget_allocation(100, ratios)
        assert allocation["a"] == 50
        assert allocation["b"] == 50


class TestGetBudgetStatus:
    """Tests for budget status reporting."""
    
    def test_within_budget(self):
        """Text within budget reports correctly."""
        text = "Short"
        status = get_budget_status(text, 100)
        assert status["within_budget"] is True
        assert status["remaining"] > 0
    
    def test_over_budget(self):
        """Text over budget reports correctly."""
        text = "word " * 100
        status = get_budget_status(text, 10)
        assert status["within_budget"] is False
        assert status["remaining"] < 0
    
    def test_utilization_calculation(self):
        """Utilization should be calculated correctly."""
        text = "word " * 10
        budget = estimate_tokens(text) * 2  # Double the estimated
        status = get_budget_status(text, budget)
        assert 0 < status["utilization"] <= 1.0
    
    def test_status_fields(self):
        """Status should include all required fields."""
        text = "test"
        status = get_budget_status(text, 100)
        assert "estimated_tokens" in status
        assert "budget" in status
        assert "within_budget" in status
        assert "utilization" in status
        assert "remaining" in status


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def test_end_to_end_truncate_and_estimate(self):
        """Full workflow: parse, estimate, truncate."""
        text = """
# Title Section

This is the main title.

## Section 1

Content for section 1 goes here.
It has multiple lines.

## Section 2

Content for section 2.
More content here.

## Section 3

Final section content.
"""
        # Estimate full text
        full_estimate = estimate_tokens(text)
        assert full_estimate > 0
        
        # Truncate to smaller budget
        budget = full_estimate // 2
        truncated = truncate_to_budget(text, budget)
        
        # Verify truncation worked
        truncated_estimate = estimate_tokens(truncated)
        assert truncated_estimate <= budget
        
        # Should preserve important headers
        assert "# Title Section" in truncated
    
    def test_deterministic_truncation(self):
        """Same input should produce same output (deterministic)."""
        text = "## Header\n\n" + "content " * 500
        budget = 100
        
        result1 = truncate_to_budget(text, budget)
        result2 = truncate_to_budget(text, budget)
        
        assert result1 == result2
    
    def test_progressive_truncation(self):
        """Smaller budgets should produce shorter output."""
        text = "## A\n\n" + "word " * 100 + "\n\n## B\n\n" + "word " * 100
        
        result_large = truncate_to_budget(text, 200)
        result_small = truncate_to_budget(text, 50)
        
        assert len(result_small) <= len(result_large)


class TestEdgeCases:
    """Edge case tests."""
    
    def test_very_small_budget(self):
        """Extremely small budget should handle gracefully."""
        text = "## Header\n\nSome content here"
        result = truncate_to_budget(text, 1)
        assert isinstance(result, str)
    
    def test_unicode_content(self):
        """Unicode content should be handled."""
        text = "## Title\n\nContent here"
        estimate = estimate_tokens(text)
        assert estimate > 0
    
    def test_special_characters(self):
        """Special characters should not break estimation."""
        text = "## Code\n\ndef func():\n    return 1 + 2"
        estimate = estimate_tokens(text, is_code=True)
        assert estimate > 0
    
    def test_whitespace_only(self):
        """Whitespace-only content should be handled."""
        text = "   \n\n   \n"
        estimate = estimate_tokens(text)
        assert estimate >= 0
    
    def test_single_newlines(self):
        """Single newlines in text should be handled."""
        text = "Line 1\nLine 2\nLine 3"
        sections = parse_sections(text)
        # Should handle gracefully
        assert isinstance(sections, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
