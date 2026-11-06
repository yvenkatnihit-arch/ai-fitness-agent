"""The one place that builds Gemini models and calls them (CLAUDE.md cost rules).

- Two tiers from .env (never hardcoded IDs): "small" (default) and "mid" (plan generation/adjustment).
- `max_tokens` is REQUIRED on every call, so no call can run away.
- Rate-limit errors (HTTP 429) are retried with backoff; if it still fails, the caller gets
  LLMBusy, whose message is safe to show the user.
- Every call, good or bad, is logged to agent_runs (tokens, cost, latency).
"""

import logging
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from app.core.config import get_settings
from app.llm.pricing import estimate_cost_usd
from app.llm.runs import record_run

logger = logging.getLogger(__name__)

Tier = Literal["small", "mid"]
RETRY_DELAYS_S = (1.0, 3.0, 8.0)   # waits before retry 1, 2, 3 (a little random jitter is added)
FRIENDLY_BUSY = "The coach is busy right now. Please try again in a minute."


class LLMBusy(Exception):
    """Rate limit or provider overload that did not clear after retries. str(e) is user-safe."""

    def __init__(self) -> None:
        super().__init__(FRIENDLY_BUSY)


class LLMFailed(Exception):
    """Any other provider failure. str(e) is user-safe; the real error is in the logs."""

    def __init__(self) -> None:
        super().__init__("Something went wrong while talking to the coach. Please try again.")


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: int


def model_name(tier: Tier) -> str:
    s = get_settings()
    return s.gemini_mid_model if tier == "mid" else s.gemini_small_model


def build_chat_model(tier: Tier, max_tokens: int, temperature: float = 0.2, json_mode: bool = False) -> Any:
    """A LangChain chat model for this tier. Imported lazily so offline tests never need the network."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    extra: dict[str, Any] = {"response_mime_type": "application/json"} if json_mode else {}
    return ChatGoogleGenerativeAI(
        model=model_name(tier),
        api_key=get_settings().gemini_api_key.get_secret_value(),
        max_output_tokens=max_tokens,
        temperature=temperature,
        max_retries=0,   # we retry ourselves, so we can log and cap it
        **extra,
    )


def is_rate_limit(error: Exception) -> bool:
    """429 / RESOURCE_EXHAUSTED / 503 overloaded: worth waiting and retrying."""
    text = f"{type(error).__name__} {error}".lower()
    return any(s in text for s in ("429", "resource_exhausted", "rate limit", "quota", "503", "unavailable", "overloaded"))


def _usage(message: Any) -> tuple[int, int, int]:
    u = getattr(message, "usage_metadata", None) or {}
    details = u.get("input_token_details") or {}
    return int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)), int(details.get("cache_read", 0))


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in content)


def call_llm(
    tier: Tier,
    messages: Sequence[Any],
    *,
    flow: str,
    node: str,
    max_tokens: int,
    user_id: UUID | None = None,
    temperature: float = 0.2,
    json_mode: bool = False,
    model: Any | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> LLMResult:
    """One logged LLM call. `model` lets tests pass a fake; `sleep` lets them skip the waiting."""
    if max_tokens <= 0:
        raise ValueError("max_tokens must be a positive number")
    name = model_name(tier)
    chat = model if model is not None else build_chat_model(tier, max_tokens, temperature, json_mode)
    started = time.monotonic()

    def log(status: str, tokens: tuple[int, int, int] = (0, 0, 0), code: str | None = None) -> int:
        ms = int((time.monotonic() - started) * 1000)
        record_run(
            user_id=user_id, flow=flow, node=node, model=name, input_tokens=tokens[0], output_tokens=tokens[1],
            cached_tokens=tokens[2], cost_usd=estimate_cost_usd(name, *tokens), latency_ms=ms, status=status,
            error_code=code,
        )
        return ms

    for attempt in range(len(RETRY_DELAYS_S) + 1):
        try:
            reply = chat.invoke(list(messages))
        except Exception as error:  # noqa: BLE001 - classified below
            if is_rate_limit(error):
                if attempt < len(RETRY_DELAYS_S):
                    sleep(RETRY_DELAYS_S[attempt] + random.uniform(0, 0.5))
                    continue
                log("rate_limited", code=type(error).__name__[:80])
                raise LLMBusy() from error
            logger.exception("LLM call failed (flow=%s node=%s)", flow, node)
            log("error", code=type(error).__name__[:80])
            raise LLMFailed() from error
        tokens = _usage(reply)
        ms = log("ok", tokens)
        return LLMResult(_text_of(reply.content).strip(), name, *tokens, estimate_cost_usd(name, *tokens), ms)
    raise LLMFailed()   # unreachable; keeps type checkers happy
