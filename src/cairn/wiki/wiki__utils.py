from collections.abc import Iterable

from cairn.domain import Artifact, SourceRef


def _first_paragraph(markdown: str) -> str:
    chunks = markdown.strip().split("\n\n", 1)
    head = chunks[0] if chunks else ""
    head = head.lstrip("#").strip()
    return head[:500]


def _avg_confidence(artifacts: list[Artifact]) -> float:
    if not artifacts:
        return 0.0
    return sum(a.confidence.score for a in artifacts) / len(artifacts)


def _dedupe_refs(refs: Iterable[SourceRef]) -> list[SourceRef]:
    seen: dict[tuple[str, str], SourceRef] = {}
    for ref in refs:
        seen.setdefault((ref.system.value, ref.external_id), ref)
    return list(seen.values())
