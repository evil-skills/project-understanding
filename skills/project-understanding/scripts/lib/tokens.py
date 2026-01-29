"""
Token Budgeting Module

Provides utilities for estimating token counts in text and truncating
to specified budgets while preserving section boundaries.

Token Estimation:
- Uses character-based heuristic (1 token ≈ 4 characters for English text)
- Accounts for code having different density than prose
- Provides conservative estimates to stay within budget

Truncation Strategy:
- Preserves section boundaries when possible
- Removes lower-priority sections first
- Adds "more available" pointers when truncating
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


# Heuristic: average English text is ~4 characters per token
# Code is denser, so we use a more conservative estimate
CHARS_PER_TOKEN = 3.5

# Code characters per token (more conservative for code-heavy text)
CODE_CHARS_PER_TOKEN = 3.0


def estimate_tokens(text: str, is_code: bool = False) -> int:
    """
    Estimate the number of tokens in a text string.
    
    Uses a simple character-based heuristic. This is intentionally conservative
    to avoid exceeding actual token budgets.
    
    Args:
        text: The text to estimate tokens for
        is_code: Whether the text is primarily code (more conservative estimate)
    
    Returns:
        Estimated token count (integer, always >= 0)
    
    Examples:
        >>> estimate_tokens("Hello world")
        3
        >>> estimate_tokens("def foo():\\n    pass", is_code=True)
        6
    
    Note:
        This is a heuristic and may differ from actual tokenizer counts.
        It is designed to be conservative (over-estimate) to stay within budgets.
    """
    if not text:
        return 0
    
    chars_per_tok = CODE_CHARS_PER_TOKEN if is_code else CHARS_PER_TOKEN
    return max(1, int(len(text) / chars_per_tok))


def estimate_tokens_batch(texts: List[str], is_code: bool = False) -> List[int]:
    """
    Estimate tokens for multiple text strings.
    
    Args:
        texts: List of texts to estimate
        is_code: Whether texts are primarily code
    
    Returns:
        List of estimated token counts
    """
    return [estimate_tokens(t, is_code) for t in texts]


@dataclass
class Section:
    """Represents a section of text with a header."""
    header: str
    content: str
    priority: int = 0
    
    def total_text(self) -> str:
        """Get the full text including header."""
        return f"{self.header}\n{self.content}"
    
    def token_count(self, is_code: bool = False) -> int:
        """Estimate tokens in this section."""
        return estimate_tokens(self.total_text(), is_code)


def parse_sections(text: str) -> List[Section]:
    """
    Parse text into sections based on markdown headers.
    
    Args:
        text: Markdown-formatted text with headers
    
    Returns:
        List of Section objects
    """
    sections = []
    
    # Split on markdown headers (## Header or ### Header)
    pattern = r'\n(?=#{1,3}[^#])'
    parts = re.split(pattern, '\n' + text)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Extract header
        lines = part.split('\n', 1)
        header = lines[0].strip()
        content = lines[1] if len(lines) > 1 else ''
        
        # Determine priority based on header level
        priority = 0
        if header.startswith('# '):
            priority = 10  # Title - never truncate
        elif header.startswith('## '):
            priority = 5   # Major section
        elif header.startswith('### '):
            priority = 3   # Subsection
        
        sections.append(Section(header=header, content=content, priority=priority))
    
    return sections


def truncate_to_budget(
    text: str,
    budget_tokens: int,
    is_code: bool = False,
    preserve_priority: bool = True
) -> str:
    """
    Truncate text to fit within a token budget.
    
    Uses a section-aware truncation strategy that:
    1. Removes lower-priority sections first
    2. Within sections, truncates at paragraph boundaries
    3. Preserves section headers when possible
    4. Adds "more available" pointers when truncating
    
    Args:
        text: The text to truncate
        budget_tokens: Maximum tokens allowed
        is_code: Whether text is primarily code
        preserve_priority: Whether to preserve high-priority sections
    
    Returns:
        Truncated text within budget
    
    Examples:
        >>> text = "## Header\\n\\nContent here.\\n\\n## Footer\\n\\nMore."
        >>> result = truncate_to_budget(text, 10)
        >>> "## Header" in result
        True
    """
    if not text:
        return ''
    
    current_tokens = estimate_tokens(text, is_code)
    
    # If within budget, return as-is
    if current_tokens <= budget_tokens:
        return text
    
    # Parse into sections
    sections = parse_sections(text)
    
    if not sections:
        # No sections found, do simple truncation
        return _simple_truncate(text, budget_tokens, is_code)
    
    # Sort by priority (higher priority first if preserving)
    if preserve_priority:
        sections.sort(key=lambda s: -s.priority)
    
    # Keep sections until budget exhausted
    result_sections = []
    used_tokens = 0
    
    for section in sections:
        section_tokens = section.token_count(is_code)
        
        if used_tokens + section_tokens <= budget_tokens:
            result_sections.append(section)
            used_tokens += section_tokens
        else:
            # Try to partially include this section
            remaining = budget_tokens - used_tokens
            if remaining > 50:  # Only if we have reasonable space
                partial = _truncate_section(section, remaining, is_code)
                if partial:
                    result_sections.append(partial)
            break
    
    # Sort back to original order
    result_sections.sort(key=lambda s: text.find(s.header))
    
    # Build result
    result = '\n\n'.join(s.total_text() for s in result_sections)
    
    # Add truncation notice
    if estimate_tokens(result, is_code) < current_tokens:
        truncated_count = len(sections) - len(result_sections)
        if truncated_count > 0:
            result += f"\n\n---\n[{truncated_count} more sections available via zoom]"
    
    return result


def _simple_truncate(text: str, budget_tokens: int, is_code: bool = False) -> str:
    """
    Simple truncation without section awareness.
    
    Truncates at word/line boundaries when possible.
    """
    chars_per_tok = CODE_CHARS_PER_TOKEN if is_code else CHARS_PER_TOKEN
    target_chars = int(budget_tokens * chars_per_tok)
    
    if len(text) <= target_chars:
        return text
    
    # Try to truncate at paragraph boundary
    truncated = text[:target_chars]
    last_para = truncated.rfind('\n\n')
    last_line = truncated.rfind('\n')
    last_space = truncated.rfind(' ')
    
    # Prefer earlier boundaries
    if last_para > target_chars * 0.7:
        truncated = truncated[:last_para]
    elif last_line > target_chars * 0.8:
        truncated = truncated[:last_line]
    elif last_space > target_chars * 0.9:
        truncated = truncated[:last_space]
    
    return truncated + "\n\n---\n[Content truncated - more available via zoom]"


def _truncate_section(section: Section, budget_tokens: int, is_code: bool = False) -> Optional[Section]:
    """
    Truncate a single section to fit within budget.
    
    Returns None if budget is too small to include anything meaningful.
    """
    header_tokens = estimate_tokens(section.header, is_code)
    
    if header_tokens >= budget_tokens:
        # Can't even fit the header
        return None
    
    content_budget = budget_tokens - header_tokens
    chars_per_tok = CODE_CHARS_PER_TOKEN if is_code else CHARS_PER_TOKEN
    target_chars = int(content_budget * chars_per_tok)
    
    content = section.content[:target_chars]
    
    # Try to truncate at sensible boundary
    last_para = content.rfind('\n\n')
    last_line = content.rfind('\n')
    
    if last_para > len(content) * 0.6:
        content = content[:last_para]
    elif last_line > len(content) * 0.8:
        content = content[:last_line]
    
    if content.strip():
        content += "\n\n[... more available via zoom]"
        return Section(
            header=section.header,
            content=content,
            priority=section.priority
        )
    
    return None


def calculate_budget_allocation(
    total_budget: int,
    section_ratios: dict[str, float]
) -> dict[str, int]:
    """
    Calculate token budget allocation across sections.
    
    Args:
        total_budget: Total tokens available
        section_ratios: Dict of section name to ratio (0.0-1.0)
    
    Returns:
        Dict of section name to allocated token count
    
    Example:
        >>> calculate_budget_allocation(4000, {
        ...     "header": 0.1,
        ...     "signature": 0.15,
        ...     "documentation": 0.2,
        ...     "code": 0.55
        ... })
        {'header': 400, 'signature': 600, 'documentation': 800, 'code': 2200}
    """
    allocations = {}
    total_ratio = sum(section_ratios.values())
    
    for name, ratio in section_ratios.items():
        normalized_ratio = ratio / total_ratio
        allocations[name] = int(total_budget * normalized_ratio)
    
    return allocations


def get_budget_status(text: str, budget_tokens: int, is_code: bool = False) -> dict:
    """
    Get status of text relative to a budget.
    
    Returns dict with:
    - estimated_tokens: Current token estimate
    - budget: Budget limit
    - within_budget: Whether within limit
    - utilization: Percentage of budget used (0.0-1.0)
    - remaining: Tokens remaining (negative if over)
    """
    estimated = estimate_tokens(text, is_code)
    remaining = budget_tokens - estimated
    
    return {
        "estimated_tokens": estimated,
        "budget": budget_tokens,
        "within_budget": estimated <= budget_tokens,
        "utilization": estimated / budget_tokens if budget_tokens > 0 else 0,
        "remaining": remaining
    }
