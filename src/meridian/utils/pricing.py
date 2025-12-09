import os
import json
import structlog
from typing import Dict, TypedDict, Optional
from datetime import datetime, timedelta

logger = structlog.get_logger()

# Version of the pricing table. Format: YYYY-MM
PRICING_VERSION = "2025-01"


class PriceRates(TypedDict):
    input: float
    output: float


# Pricing Table (USD per 1M tokens)
# Sources checked Dec 2024
DEFAULT_PRICING: Dict[str, PriceRates] = {
    # Anthropic
    "claude-4.5-opus": {"input": 5.00, "output": 25.00},
    "claude-4.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-4.5-haiku": {"input": 1.00, "output": 5.00},
    # Cohere
    "command-a": {"input": 2.50, "output": 10.00},
    "command-r": {"input": 0.15, "output": 0.60},
    "embed-4": {"input": 0.12, "output": 0.0},
    # OpenAI
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
    "text-embedding-ada-002": {"input": 0.10, "output": 0.0},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5-pro": {"input": 15.00, "output": 120.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    # Fallback
    "default": {"input": 5.00, "output": 15.00},
}

_merged_pricing: Optional[Dict[str, PriceRates]] = None
_checked_freshness = False


def _get_pricing() -> Dict[str, PriceRates]:
    """
    Returns the pricing table, merging default with optional custom file.
    Only loads once.
    """
    global _merged_pricing, _checked_freshness

    # 1. Freshness Check (Once)
    if not _checked_freshness:
        _check_pricing_freshness()
        _checked_freshness = True

    if _merged_pricing is not None:
        return _merged_pricing

    # Start with defaults
    pricing = DEFAULT_PRICING.copy()

    # 2. Check for Override File
    custom_file = os.environ.get("MERIDIAN_CUSTOM_PRICING_FILE")
    if custom_file:
        try:
            if os.path.exists(custom_file):
                with open(custom_file, "r") as f:
                    custom_data = json.load(f)
                    # Merge logic: overwrite keys
                    for k, v in custom_data.items():
                        if "input" in v and "output" in v:
                            pricing[k] = {
                                "input": float(v["input"]),
                                "output": float(v["output"]),
                            }
                logger.info("loaded_custom_pricing", file=custom_file)
            else:
                logger.warning("custom_pricing_file_not_found", file=custom_file)
        except Exception as e:
            logger.error("failed_to_load_custom_pricing", error=str(e))

    _merged_pricing = pricing
    return pricing


def _check_pricing_freshness() -> None:
    """Logs a warning if the internal pricing version is > 6 months old."""
    try:
        version_date = datetime.strptime(PRICING_VERSION, "%Y-%m")
        # Check if > 180 days (approx 6 months)
        if datetime.now() - version_date > timedelta(days=180):
            logger.warning(
                "pricing_data_stale",
                version=PRICING_VERSION,
                msg="Pricing data may be outdated (>6 months). Set MERIDIAN_CUSTOM_PRICING_FILE or upgrade Meridian.",
            )
    except Exception:  # nosec
        pass


def estimate_cost(model: str, input_tokens: int, output_tokens: int = 0) -> float:
    """
    Estimates the cost of a request based on the model and token counts.

    Args:
        model: Model identifier (e.g., 'gpt-4o'). Defaults to 'default' pricing if unknown.
        input_tokens: Number of input/context tokens.
        output_tokens: Number of output/generated tokens.

    Returns:
        Estimated cost in USD.
    """
    pricing = _get_pricing()

    rates = pricing.get(model)
    if not rates:
        # Try finding a matching prefix or fallback
        # e.g. "gpt-4o-2024..." might match "gpt-4o" if we wanted fuzzy matching,
        # but exact match + default is safer for now.
        rates = pricing["default"]

    cost = (input_tokens / 1_000_000 * rates["input"]) + (
        output_tokens / 1_000_000 * rates["output"]
    )
    return round(cost, 6)
