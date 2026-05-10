"""Optional FastAPI surface.

Exposes the `KnowledgeLayer` over HTTP. Install the `api` extra to use:

    pip install 'cairn[api]'

The router is intentionally small: it wires up ingestion, querying, and the
evaluation loop. Streaming endpoints use Server-Sent Events; the spec also
mentions Pusher and WebSocket — those are easy to add behind the same
business-logic methods on the layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..errors import ConfigError
from ..schemas import ArtifactType, SourceDocument

if TYPE_CHECKING:  # pragma: no cover - only for type checking
    from fastapi import FastAPI


def build_app(layer: Any) -> FastAPI:
    """Build a FastAPI app bound to a `KnowledgeLayer` instance."""
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:  # pragma: no cover
        raise ConfigError("api extra not installed; pip install 'cairn[api]'") from exc

    app = FastAPI(title="cairn", version="0.1.0")

    class IngestRequest(BaseModel):
        documents: list[SourceDocument]
        artifact_type: ArtifactType = ArtifactType.ACCOUNT_INTELLIGENCE

    class QueryRequest(BaseModel):
        intent: str
        token_budget: int = 4000
        entity_hints: list[str] = []
        artifact_types: list[ArtifactType] = []
        permissions: list[str] = []
        min_confidence: float = 0.0
        max_age_days: int | None = None
        top_k: int = 10
        graph_depth: int = 1

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest")
    async def ingest(req: IngestRequest) -> dict[str, Any]:
        await layer.ingest_documents(req.documents)
        result = await layer.process_buffer(artifact_type=req.artifact_type)
        return {
            "documents": result.documents,
            "facts": len(result.facts),
            "entities": len(result.entities),
            "artifacts": [a.artifact_id for a in result.artifacts],
        }

    @app.post("/query")
    async def query(req: QueryRequest) -> dict[str, Any]:
        try:
            ctx = await layer.query(
                req.intent,
                token_budget=req.token_budget,
                entity_hints=req.entity_hints,
                artifact_types=req.artifact_types,
                permissions=req.permissions,
                min_confidence=req.min_confidence,
                max_age_days=req.max_age_days,
                top_k=req.top_k,
                graph_depth=req.graph_depth,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "rendered": ctx.render(),
            "fragments": [f.model_dump() for f in ctx.fragments],
            "total_tokens": ctx.total_tokens,
            "dropped": ctx.dropped_fragment_ids,
        }

    @app.post("/wiki/refresh")
    async def refresh() -> dict[str, Any]:
        pages = await layer.refresh_wiki()
        return {"pages": [p.artifact_id for p in pages]}

    @app.get("/evaluate")
    async def evaluate(check_contradictions: bool = False) -> dict[str, Any]:
        issues = await layer.evaluate(check_contradictions=check_contradictions)
        return {
            "issues": [
                {
                    "kind": i.kind.value,
                    "severity": i.severity,
                    "artifact_ids": i.artifact_ids,
                    "description": i.description,
                }
                for i in issues
            ]
        }

    return app


__all__ = ["build_app"]
