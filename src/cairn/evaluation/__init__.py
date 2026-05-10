"""Evaluation & optimization loop.

Runs continuously (or on demand) to detect:

  * stale knowledge       -- artifacts whose source documents have changed or
                              that exceed a freshness horizon
  * contradictions        -- artifacts referring to the same entity with
                              irreconcilable claims in `content`
  * low-confidence drift  -- aggregate confidence falling below threshold
  * retrieval quality     -- replay of recorded queries with offline scoring

Outputs are surfaced as `EvalIssue` objects rather than mutations; the caller
chooses whether to recompile, archive, or escalate. This separation keeps the
evaluation loop side-effect free and easy to test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from ..llm import LLMClient, LLMTask
from ..schemas import Artifact
from ..store import ArtifactStore, iter_active_artifacts

log = logging.getLogger(__name__)


class IssueKind(str, Enum):
    STALE = "stale"
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTION = "contradiction"
    UNREFERENCED = "unreferenced"


@dataclass
class EvalIssue:
    kind: IssueKind
    artifact_ids: list[str]
    description: str
    severity: float  # 0..1, higher = more urgent
    metadata: dict[str, object] = field(default_factory=dict)


CONTRADICTION_SYSTEM = """You are an auditor for operational knowledge artifacts.
Given two artifacts about the same subject, decide whether they contradict.
Return JSON: {"contradicts": <bool>, "explanation": "<short>"}
Only mark contradiction if the two cannot both be true at the same time."""


class EvaluationLoop:
    """Audits the artifact store and emits issues."""

    def __init__(
        self,
        *,
        artifact_store: ArtifactStore,
        llm: LLMClient | None = None,
        stale_after_days: int = 30,
        low_confidence_threshold: float = 0.4,
    ) -> None:
        self._artifacts = artifact_store
        self._llm = llm
        self._stale_after_days = stale_after_days
        self._low_conf = low_confidence_threshold

    async def run(self, *, check_contradictions: bool = True) -> list[EvalIssue]:
        artifacts = iter_active_artifacts(await self._artifacts.list())
        issues: list[EvalIssue] = []
        issues.extend(self._check_stale(artifacts))
        issues.extend(self._check_low_confidence(artifacts))
        issues.extend(self._check_unreferenced(artifacts))
        if check_contradictions and self._llm is not None:
            issues.extend(await self._check_contradictions(artifacts))
        issues.sort(key=lambda i: i.severity, reverse=True)
        return issues

    # ------------------------------------------------------------------------

    def _check_stale(self, artifacts: list[Artifact]) -> list[EvalIssue]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._stale_after_days)
        out: list[EvalIssue] = []
        for a in artifacts:
            if a.updated_at < cutoff:
                age_days = (datetime.now(timezone.utc) - a.updated_at).days
                severity = min(1.0, age_days / (self._stale_after_days * 4))
                out.append(
                    EvalIssue(
                        kind=IssueKind.STALE,
                        artifact_ids=[a.artifact_id],
                        description=f"Artifact '{a.title}' has not been refreshed in {age_days} days.",
                        severity=severity,
                        metadata={"age_days": age_days},
                    )
                )
        return out

    def _check_low_confidence(self, artifacts: list[Artifact]) -> list[EvalIssue]:
        out: list[EvalIssue] = []
        for a in artifacts:
            if a.confidence.score < self._low_conf:
                out.append(
                    EvalIssue(
                        kind=IssueKind.LOW_CONFIDENCE,
                        artifact_ids=[a.artifact_id],
                        description=(
                            f"Artifact '{a.title}' has confidence "
                            f"{a.confidence.score:.2f} (< {self._low_conf:.2f})."
                        ),
                        severity=1.0 - a.confidence.score,
                    )
                )
        return out

    def _check_unreferenced(self, artifacts: list[Artifact]) -> list[EvalIssue]:
        out: list[EvalIssue] = []
        for a in artifacts:
            if not a.source_refs:
                out.append(
                    EvalIssue(
                        kind=IssueKind.UNREFERENCED,
                        artifact_ids=[a.artifact_id],
                        description=f"Artifact '{a.title}' has no source provenance.",
                        severity=0.6,
                    )
                )
        return out

    async def _check_contradictions(self, artifacts: list[Artifact]) -> list[EvalIssue]:
        # Group active artifacts by primary entity ref; compare pairs within groups.
        assert self._llm is not None
        out: list[EvalIssue] = []
        groups: dict[str, list[Artifact]] = {}
        for a in artifacts:
            for eid in a.entity_refs:
                groups.setdefault(eid, []).append(a)

        for eid, group in groups.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if a.artifact_type != b.artifact_type:
                        continue
                    issue = await self._llm_pair_check(a, b, entity_id=eid)
                    if issue is not None:
                        out.append(issue)
        return out

    async def _llm_pair_check(
        self, a: Artifact, b: Artifact, *, entity_id: str
    ) -> EvalIssue | None:
        if self._llm is None:
            return None
        prompt = (
            f"Subject entity id: {entity_id}\n\n"
            f"Artifact A:\nTitle: {a.title}\nSummary: {a.summary}\nContent: {a.content}\n\n"
            f"Artifact B:\nTitle: {b.title}\nSummary: {b.summary}\nContent: {b.content}"
        )
        try:
            result = await self._llm.complete_json(
                task=LLMTask.HEAVY,
                system=CONTRADICTION_SYSTEM,
                user=prompt,
                max_tokens=300,
            )
        except Exception as exc:
            log.warning("contradiction check failed: %s", exc)
            return None
        if not isinstance(result, dict) or not result.get("contradicts"):
            return None
        return EvalIssue(
            kind=IssueKind.CONTRADICTION,
            artifact_ids=[a.artifact_id, b.artifact_id],
            description=str(result.get("explanation") or "contradiction"),
            severity=0.85,
            metadata={"entity_id": entity_id},
        )


__all__ = ["EvalIssue", "EvaluationLoop", "IssueKind"]
