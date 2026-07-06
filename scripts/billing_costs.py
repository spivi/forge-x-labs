"""Anthropic billing API fetching and cost calculation.

Handles API communication, model pricing lookup, token cost calculation,
and aggregation of API-billed usage (excluding subscription).
"""

from __future__ import annotations

import sys

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

ANTHROPIC_API_BASE = "https://api.anthropic.com/v1/organizations"
CACHE_WRITE_MULTIPLIER = 1.25  # cache write = 1.25x input price
CACHE_READ_MULTIPLIER = 0.10  # cache read = 0.10x input price


def fetch_usage(
    url: str,
    params: list[tuple[str, str]],
    headers: dict,  # type: ignore[type-arg]
) -> dict | None:  # type: ignore[type-arg]
    """Fetch usage data, preferring httpx with urllib fallback."""
    try:
        if HAS_HTTPX:
            return _fetch_with_httpx(url, params, headers)
        return _fetch_with_urllib(url, params, headers)
    except Exception as exc:
        print(f"WARNING: Billing API request failed: {exc}", file=sys.stderr)
        return None


def _fetch_with_httpx(
    url: str,
    params: list[tuple[str, str]],
    headers: dict,  # type: ignore[type-arg]
) -> dict | None:  # type: ignore[type-arg]
    """Fetch usage via httpx."""
    resp = httpx.get(url, params=params, headers=headers, timeout=10.0)
    if resp.status_code != 200:
        print(f"WARNING: Billing API returned {resp.status_code}", file=sys.stderr)
        return None
    return resp.json()


def _fetch_with_urllib(
    url: str,
    params: list[tuple[str, str]],
    headers: dict,  # type: ignore[type-arg]
) -> dict | None:  # type: ignore[type-arg]
    """Fetch usage via urllib (fallback when httpx unavailable)."""
    import json
    import urllib.parse
    import urllib.request

    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def model_pricing(
    model: str,
    pricing: dict,  # type: ignore[type-arg]
) -> tuple[float, float]:
    """Get (input_per_1m, output_per_1m) for a model from pricing config.

    Generic substring match over every key in `pricing.anthropic` in budgets.yml
    (family keys like `fable`/`opus`/`sonnet`/`haiku` as well as version-pinned
    keys like `claude-fable-5`), so adding a `fable:` family entry to budgets.yml
    (FXL-102) is sufficient here -- no code change needed, this already matches
    `claude-fable-5` via the `fable` family key.

    Falls back to Sonnet 4.5 pricing if model not found.
    """
    anthropic_pricing = pricing.get("anthropic", {})
    for key, rates in anthropic_pricing.items():
        if key in model:
            return (
                float(rates.get("input_per_1m", 3.0)),
                float(rates.get("output_per_1m", 15.0)),
            )
    return (3.0, 15.0)  # default to Sonnet 4.5


def calculate_token_cost(
    result: dict,  # type: ignore[type-arg]
    pricing: dict,  # type: ignore[type-arg]
) -> float:
    """Calculate dollar cost from a usage_report/messages result entry."""
    model_name = result.get("model") or ""
    input_per_1m, output_per_1m = model_pricing(model_name, pricing)
    cache_creation = result.get("cache_creation", {})
    cache_w = cache_creation.get("ephemeral_5m_input_tokens", 0)
    cache_w += cache_creation.get("ephemeral_1h_input_tokens", 0)
    tokens = {
        "input": result.get("uncached_input_tokens", 0),
        "output": result.get("output_tokens", 0),
        "cache_write": cache_w,
        "cache_read": result.get("cache_read_input_tokens", 0),
    }
    cost = (
        tokens["input"] * input_per_1m
        + tokens["cache_write"] * input_per_1m * CACHE_WRITE_MULTIPLIER
        + tokens["cache_read"] * input_per_1m * CACHE_READ_MULTIPLIER
        + tokens["output"] * output_per_1m
    ) / 1_000_000
    return cost


def sum_api_key_usage(
    data: dict,  # type: ignore[type-arg]
    pricing: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Sum API-billed costs from usage_report/messages, excluding subscription.

    Filters out api_key_id=null entries (Claude Code subscription usage).
    """
    total = 0.0
    by_key: dict[str, float] = {}
    for bucket in data.get("data", []):
        for result in bucket.get("results", []):
            key_id = result.get("api_key_id")
            if key_id is None:
                continue  # skip subscription usage
            cost = calculate_token_cost(result, pricing)
            total += cost
            by_key[key_id] = by_key.get(key_id, 0.0) + cost
    return {"total": total, "by_key": by_key}
