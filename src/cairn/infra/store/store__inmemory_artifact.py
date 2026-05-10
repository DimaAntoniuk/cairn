from cairn.domain import Artifact, ArtifactType, StoreError
from cairn.domain.store__ports import IArtifactStore


class InMemoryArtifactStore(IArtifactStore):
    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    async def put(self, artifact: Artifact) -> Artifact:
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    async def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    async def list(
        self,
        *,
        artifact_type: ArtifactType | None = None,
        entity_ref: str | None = None,
    ) -> list[Artifact]:
        def keep(a: Artifact) -> bool:
            if artifact_type is not None and a.artifact_type != artifact_type:
                return False
            if entity_ref is not None and entity_ref not in a.entity_refs:  # noqa: SIM103
                return False
            return True

        return [a for a in self._artifacts.values() if keep(a)]

    async def supersede(self, old_id: str, new_artifact: Artifact) -> Artifact:
        old = self._artifacts.get(old_id)
        if old is None:
            raise StoreError(f"cannot supersede unknown artifact {old_id}")
        bumped = new_artifact.model_copy(
            update={
                "version": old.version + 1,
                "superseded_by": None,
            }
        )
        self._artifacts[bumped.artifact_id] = bumped
        self._artifacts[old_id] = old.model_copy(update={"superseded_by": bumped.artifact_id})
        return bumped
