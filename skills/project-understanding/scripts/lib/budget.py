"""
Budget management with automatic model context detection.

Provides utilities for:
- Detecting model context constraints
- Calculating appropriate budgets based on context
- Falling back to config defaults
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ModelContext:
    """Model context information."""
    model_name: Optional[str] = None
    context_window: int = 8192
    max_output_tokens: int = 4096
    source: str = "default"


# Known model context windows
MODEL_CONTEXT_WINDOWS: Dict[str, int] = {
    # OpenAI models
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    
    # Anthropic models
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "claude-instant": 100000,
    
    # Common aliases
    "opus": 200000,
    "sonnet": 200000,
    "haiku": 200000,
}


def detect_model_context() -> ModelContext:
    """
    Detect model context from environment variables.
    
    Checks various environment variables commonly set by AI coding tools:
    - PUI_MODEL: Explicit model name
    - OPENAI_MODEL: OpenAI model name
    - ANTHROPIC_MODEL: Anthropic model name
    - AIDER_MODEL: Aider editor model
    - CURSOR_MODEL: Cursor editor model
    
    Returns:
        ModelContext with detected settings
    """
    # Check for explicit model setting
    model_name = (
        os.getenv("PUI_MODEL") or
        os.getenv("OPENAI_MODEL") or
        os.getenv("ANTHROPIC_MODEL") or
        os.getenv("AIDER_MODEL") or
        os.getenv("CURSOR_MODEL")
    )
    
    if model_name:
        # Normalize model name
        model_name = model_name.lower().strip()
        
        # Find matching context window
        for prefix, context in MODEL_CONTEXT_WINDOWS.items():
            if model_name.startswith(prefix.lower()):
                return ModelContext(
                    model_name=model_name,
                    context_window=context,
                    max_output_tokens=min(context // 2, 4096),
                    source="environment"
                )
    
    # Check for explicit context window
    context_window = os.getenv("PUI_CONTEXT_WINDOW")
    if context_window:
        try:
            window = int(context_window)
            return ModelContext(
                model_name=model_name or "custom",
                context_window=window,
                max_output_tokens=min(window // 2, 4096),
                source="environment"
            )
        except ValueError:
            pass
    
    # Default fallback
    return ModelContext(source="default")


def calculate_auto_budget(
    context: ModelContext,
    pack_type: str = "repomap",
    reserved_for_input: float = 0.5,
    safety_margin: float = 0.9
) -> int:
    """
    Calculate budget based on model context.
    
    Args:
        context: Model context information
        pack_type: Type of pack (repomap, zoom, impact, find)
        reserved_for_input: Fraction of context to reserve for input
        safety_margin: Safety margin to apply
    
    Returns:
        Calculated token budget
    """
    # Available tokens after reserving space for input
    available = int(context.context_window * reserved_for_input * safety_margin)
    
    # Pack-specific ratios
    ratios = {
        "repomap": 0.3,      # Overview needs less
        "zoom": 0.15,        # Detail pack needs moderate
        "impact": 0.2,       # Impact analysis needs moderate
        "find": 0.05,        # Find results need minimal
    }
    
    ratio = ratios.get(pack_type, 0.2)
    budget = int(available * ratio)
    
    # Apply sensible minimums and maximums
    min_budgets = {
        "repomap": 2000,
        "zoom": 1000,
        "impact": 1500,
        "find": 500,
    }
    
    max_budgets = {
        "repomap": 16000,
        "zoom": 8000,
        "impact": 12000,
        "find": 2000,
    }
    
    budget = max(budget, min_budgets.get(pack_type, 1000))
    budget = min(budget, max_budgets.get(pack_type, 8000))
    
    return budget


def resolve_budget(
    budget_arg: str,
    pack_type: str = "repomap",
    config_budget: Optional[int] = None
) -> int:
    """
    Resolve budget from CLI argument.
    
    Args:
        budget_arg: Budget argument (number or "auto")
        pack_type: Type of pack being generated
        config_budget: Budget from configuration file
    
    Returns:
        Resolved token budget
    """
    if budget_arg == "auto":
        context = detect_model_context()
        return calculate_auto_budget(context, pack_type)
    
    # Try to parse as integer
    try:
        return int(budget_arg)
    except ValueError:
        pass
    
    # Fall back to config default
    if config_budget is not None:
        return config_budget
    
    # Ultimate fallback
    defaults = {
        "repomap": 8000,
        "zoom": 4000,
        "impact": 6000,
        "find": 2000,
    }
    return defaults.get(pack_type, 4000)


def get_budget_info(budget: int, pack_type: str = "repomap") -> Dict[str, Any]:
    """
    Get information about the budget for display.
    
    Returns:
        Dict with budget details
    """
    context = detect_model_context()
    
    return {
        "budget": budget,
        "pack_type": pack_type,
        "model": context.model_name or "unknown",
        "context_window": context.context_window,
        "source": context.source,
    }
