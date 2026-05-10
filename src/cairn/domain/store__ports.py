from abc import ABC, abstractmethod
from collections.abc import Sequence

from .artifact__types import Artifact, ArtifactType
from .entity__types import Entity, EntityType
from .relationship__types import Relationship, RelationshipType


class IGraphStore(ABC):
    @abstractmethod
    async def upsert_entity(self, entity: Entity) -> Entity: ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Entity | None: ...

    @abstractmethod
    async def find_entities(
        self, *, name: str | None = None, entity_type: EntityType | None = None
    ) -> list[Entity]: ...

    @abstractmethod
    async def upsert_relationship(self, rel: Relationship) -> Relationship: ...

    @abstractmethod
    async def neighbors(
        self,
        entity_id: str,
        *,
        relationship_types: Sequence[RelationshipType] | None = None,
        depth: int = 1,
    ) -> list[Entity]: ...

    @abstractmethod
    async def relationships_of(
        self, entity_id: str, *, direction: str = "both"
    ) -> list[Relationship]: ...


class IEmbedder(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]: ...


class IVectorStore(ABC):
    @abstractmethod
    async def upsert(
        self,
        *,
        id: str,
        vector: list[float],
        text: str,
        metadata: dict[str, object] | None = None,
    ) -> None: ...

    @abstractmethod
    async def search(
        self, *, vector: list[float], top_k: int = 10
    ) -> list[tuple[str, float, str, dict[str, object]]]: ...


class IArtifactStore(ABC):
    @abstractmethod
    async def put(self, artifact: Artifact) -> Artifact: ...

    @abstractmethod
    async def get(self, artifact_id: str) -> Artifact | None: ...

    @abstractmethod
    async def list(
        self,
        *,
        artifact_type: ArtifactType | None = None,
        entity_ref: str | None = None,
    ) -> list[Artifact]: ...

    @abstractmethod
    async def supersede(self, old_id: str, new_artifact: Artifact) -> Artifact: ...


__all__ = [
    "IArtifactStore",
    "IEmbedder",
    "IGraphStore",
    "IVectorStore",
]
