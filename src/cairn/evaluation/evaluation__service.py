import logging
from datetime import UTC, datetime, timedelta

from cairn.domain import Artifact, EvalIssue, IssueKind, iter_active_artifacts
from cairn.domain.llm__ports import ILLMClient
from cairn.domain.store__ports import IArtifactStore

from .evaluation__prompts import CONTRADICTION_SYSTEM
from .evaluation__types import ContradictionResponse

log = logging.getLogger(__name__)


class EvaluationLoop:
    def __init__(
        self,
        *,
        artifact_store: IArtifactStore,
        llm: ILLMClient | None = None,
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

    def _check_stale(self, artifacts: list[Artifact]) -> list[EvalIssue]:
        cutoff = datetime.now(UTC) - timedelta(days=self._stale_after_days)
        out: list[EvalIssue] = []
        for a in artifacts:
            if a.updated_at < cutoff:
                age_days = (datetime.now(UTC) - a.updated_at).days
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
            f"{CONTRADICTION_SYSTEM}\n\n"
            f"Subject entity id: {entity_id}\n\n"
            f"Artifact A:\nTitle: {a.title}\nSummary: {a.summary}\nContent: {a.content}\n\n"
            f"Artifact B:\nTitle: {b.title}\nSummary: {b.summary}\nContent: {b.content}"
        )
        try:
            result = await self._llm.astructured_predict(
                ContradictionResponse, prompt, max_tokens=300,
            )
        except Exception as exc:
            log.warning("contradiction check failed: %s", exc)
            return None
        if not result.contradicts:
            return None
        return EvalIssue(
            kind=IssueKind.CONTRADICTION,
            artifact_ids=[a.artifact_id, b.artifact_id],
            description=result.explanation or "contradiction",
            severity=0.85,
            metadata={"entity_id": entity_id},
        )


__all__ = ["EvaluationLoop"]
