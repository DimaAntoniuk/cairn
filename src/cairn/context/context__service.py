import hashlib
import logging
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from cairn.domain import Artifact, AssembledContext, ContextFragment
from cairn.domain.context__ports import ICompressor
from cairn.domain.llm__ports import ChatMessage, ILLMClient
from cairn.domain.retrieval__types import RetrievalResult

from .context__consts import CHARS_PER_TOKEN
from .context__types import AssemblyWeights
from .context__utils import _clamp01, estimate_tokens

log = logging.getLogger(__name__)


class LLMCompressor(ICompressor):
    def __init__(self, llm: ILLMClient) -> None:
        self._llm = llm

    async def compress(self, text: str, *, target_tokens: int) -> str:
        target_chars = target_tokens * CHARS_PER_TOKEN
        if len(text) <= target_chars:
            return text
        system = (
            "Compress the input while preserving every concrete fact, decision, "
            f"constraint, and entity name. Target length: ~{target_tokens} tokens. "
            "Do not invent. Do not add commentary."
        )
        response = await self._llm.achat(
            [
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=text),
            ],
            max_tokens=target_tokens + 64,
        )
        return response.content


class ContextAssembler:
    def __init__(
        self,
        *,
        weights: AssemblyWeights | None = None,
        compressor: ICompressor | None = None,
        recency_horizon_days: int = 90,
    ) -> None:
        self._weights = weights or AssemblyWeights()
        self._compressor = compressor
        self._recency_horizon_days = recency_horizon_days

    async def assemble(
        self,
        *,
        results: Sequence[RetrievalResult],
        token_budget: int,
        extra_fragments: Iterable[ContextFragment] = (),
        bias_artifact_ids: Iterable[str] = (),
    ) -> AssembledContext:
        bias_set = set(bias_artifact_ids)
        fragments = self._build_fragments(results, bias_set)
        fragments.extend(extra_fragments)
        fragments = self._dedupe(fragments)
        fragments.sort(key=lambda f: f.priority, reverse=True)
        return await self._fit_to_budget(fragments, token_budget)

    def _build_fragments(
        self, results: Sequence[RetrievalResult], bias_set: set[str]
    ) -> list[ContextFragment]:
        out: list[ContextFragment] = []
        for r in results:
            text = self._render_artifact(r.artifact)
            priority = self._priority_for(r, bias_set)
            out.append(
                ContextFragment(
                    text=text,
                    token_estimate=estimate_tokens(text),
                    priority=priority,
                    confidence=r.artifact.confidence,
                    source_refs=list(r.artifact.source_refs),
                    artifact_id=r.artifact.artifact_id,
                    entity_ids=list(r.artifact.entity_refs),
                )
            )
        return out

    def _priority_for(self, result: RetrievalResult, bias_set: set[str]) -> float:
        w = self._weights
        relevance = _clamp01(result.score)
        confidence = result.artifact.confidence.score
        recency = self._recency_score(result.artifact.updated_at)
        bias = 1.0 if result.artifact.artifact_id in bias_set else 0.0
        score = (
            w.relevance * relevance
            + w.confidence * confidence
            + w.recency * recency
            + w.bias * bias
        )
        return _clamp01(score)

    def _recency_score(self, updated_at: datetime) -> float:
        age_days = (datetime.now(UTC) - updated_at).total_seconds() / 86400
        if age_days <= 0:
            return 1.0
        if age_days >= self._recency_horizon_days:
            return 0.0
        return 1.0 - (age_days / self._recency_horizon_days)

    @staticmethod
    def _render_artifact(artifact: Artifact) -> str:
        body_lines = [f"# {artifact.title} ({artifact.artifact_type.value})", artifact.summary]
        if artifact.content:
            for k, v in artifact.content.items():
                body_lines.append(f"- {k}: {v}")
        if artifact.source_refs:
            srcs = ", ".join(f"{r.system.value}:{r.external_id}" for r in artifact.source_refs[:5])
            body_lines.append(f"_sources: {srcs}_")
        return "\n".join(body_lines)

    @staticmethod
    def _dedupe(fragments: list[ContextFragment]) -> list[ContextFragment]:
        seen: dict[str, ContextFragment] = {}
        for frag in fragments:
            key = hashlib.sha1(frag.text.encode("utf-8")).hexdigest()
            existing = seen.get(key)
            if existing is None or frag.priority > existing.priority:
                seen[key] = frag
        return list(seen.values())

    async def _fit_to_budget(
        self, fragments: list[ContextFragment], token_budget: int
    ) -> AssembledContext:
        chosen: list[ContextFragment] = []
        dropped: list[str] = []
        used = 0
        for frag in fragments:
            if used + frag.token_estimate <= token_budget:
                chosen.append(frag)
                used += frag.token_estimate
                continue

            remaining = token_budget - used
            if self._compressor is not None and frag.priority >= 0.5 and remaining >= 64:
                compressed = await self._compressor.compress(frag.text, target_tokens=remaining)
                shrunk = frag.model_copy(
                    update={"text": compressed, "token_estimate": estimate_tokens(compressed)}
                )
                if used + shrunk.token_estimate <= token_budget:
                    chosen.append(shrunk)
                    used += shrunk.token_estimate
                    continue
            dropped.append(frag.id)
        return AssembledContext(
            fragments=chosen,
            total_tokens=used,
            dropped_fragment_ids=dropped,
        )


__all__ = ["ContextAssembler", "LLMCompressor"]
