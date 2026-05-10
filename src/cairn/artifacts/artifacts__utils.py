from collections.abc import Iterable

from cairn.domain import SourceRef


def _dedupe_refs(refs: Iterable[SourceRef]) -> list[SourceRef]:
    seen: dict[tuple[str, str], SourceRef] = {}
    for ref in refs:
        key = (ref.system.value, ref.external_id)
        seen.setdefault(key, ref)
    return list(seen.values())
