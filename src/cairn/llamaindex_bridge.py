from typing import TYPE_CHECKING, Any

from .domain import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from llama_index.core.retrievers import BaseRetriever


def build_retriever(layer: Any, *, token_budget: int = 4000, top_k: int = 10) -> "BaseRetriever":
    try:
        from llama_index.core.retrievers import BaseRetriever
        from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
    except ImportError as exc:  # pragma: no cover
        raise ConfigError(
            "llamaindex extra not installed; pip install 'cairn[llamaindex]'"
        ) from exc

    class CairnRetriever(BaseRetriever):
        def __init__(self) -> None:
            super().__init__()

        async def _aretrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
            ctx = await layer.query(
                query_bundle.query_str,
                token_budget=token_budget,
                top_k=top_k,
            )
            nodes: list[NodeWithScore] = []
            for frag in ctx.fragments:
                node = TextNode(
                    text=frag.text,
                    id_=frag.id,
                    metadata={
                        "artifact_id": frag.artifact_id,
                        "entity_ids": frag.entity_ids,
                        "confidence": frag.confidence.score,
                        "source_refs": [
                            {"system": r.system.value, "external_id": r.external_id}
                            for r in frag.source_refs
                        ],
                    },
                )
                nodes.append(NodeWithScore(node=node, score=frag.priority))
            return nodes

        def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
            import anyio

            return anyio.run(self._aretrieve, query_bundle)

    return CairnRetriever()


__all__ = ["build_retriever"]
