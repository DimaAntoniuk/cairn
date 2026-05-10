from cairn.domain import Confidence, ContextFragment

from .context__consts import CHARS_PER_TOKEN


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def fragment_from_text(
    text: str,
    *,
    priority: float = 0.5,
    confidence: float = 1.0,
) -> ContextFragment:
    return ContextFragment(
        text=text,
        token_estimate=estimate_tokens(text),
        priority=_clamp01(priority),
        confidence=Confidence(score=_clamp01(confidence)),
    )


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))
