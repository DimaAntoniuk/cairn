import importlib.util
import os

from cairn import KnowledgeLayer
from cairn.domain import (
    Artifact,
    ArtifactType,
    Confidence,
    ConfigError,
    Entity,
    EntityType,
    SourceRef,
    SourceSystem,
)
from cairn.domain.llm__ports import ILLMClient
from cairn.infra.llm import MockLLM
from cairn.infra.llm.llm__llamaindex import LlamaIndexLLMAdapter

from .session__consts import MOCK_LABEL
from .session__types import LLMChoice, SessionConfig


def _has_module(name: str) -> bool:
    # find_spec imports parent packages and raises if one is missing, so a
    # dotted optional path needs the guard rather than a bare `is not None`.
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


# The adapter module is import-safe without the LlamaIndex/Anthropic extras (its
# heavy imports live in __init__). Only the concrete `Anthropic` LLM class needs
# the extra, so resolve that one conditionally — and bind a fallback so the name
# is always defined for the type checker.
_HAS_ANTHROPIC = _has_module("llama_index.llms.anthropic")
if _HAS_ANTHROPIC:
    from llama_index.llms.anthropic import Anthropic
else:
    Anthropic = None


def _make_llm(config: SessionConfig) -> tuple[ILLMClient, str]:
    """Pick the LLM backend, returning the client and a human-readable label."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    want_anthropic = config.llm is LLMChoice.ANTHROPIC or (
        config.llm is LLMChoice.AUTO and bool(key)
    )
    if want_anthropic:
        if Anthropic is None:
            raise ConfigError("anthropic backend unavailable; pip install 'cairn[anthropic]'")
        if not key:
            raise ConfigError("ANTHROPIC_API_KEY is not set")
        return LlamaIndexLLMAdapter(Anthropic(model=config.model)), f"anthropic · {config.model}"
    return MockLLM(default_chat=""), MOCK_LABEL


class CairnSession:
    """Holds the live ``KnowledgeLayer`` plus presentation-facing session state.

    Intentionally thin: command handling delegates straight to ``self.layer`` so
    there is exactly one implementation of the ingest/process/query pipeline.
    """

    def __init__(self, layer: KnowledgeLayer, *, llm_label: str, token_budget: int) -> None:
        self.layer = layer
        self.llm_label = llm_label
        self.token_budget = token_budget

    async def snapshot(self) -> tuple[list[Artifact], list[Entity]]:
        """Current artifacts + entities, for the sidebar."""
        artifacts = await self.layer.artifact_store.list()
        entities = await self.layer.graph_store.find_entities()
        return artifacts, entities


def build_session(config: SessionConfig) -> CairnSession:
    llm, label = _make_llm(config)
    layer = KnowledgeLayer(llm=llm)
    return CairnSession(layer, llm_label=label, token_budget=config.token_budget)


def _demo_entity(entity_type: EntityType, name: str) -> Entity:
    return Entity(entity_type=entity_type, name=name)


def _demo_artifact(
    artifact_type: ArtifactType,
    title: str,
    summary: str,
    content: dict[str, str],
    entity_refs: list[str],
) -> Artifact:
    return Artifact(
        artifact_type=artifact_type,
        title=title,
        summary=summary,
        content=content,
        entity_refs=entity_refs,
        source_refs=[SourceRef(system=SourceSystem.MANUAL, external_id="demo")],
        confidence=Confidence(score=0.82),
    )


async def seed_demo(session: CairnSession) -> int:
    """Preload a few artifacts/entities directly into the stores.

    Bypasses the LLM pipeline so the UI is explorable without an API key. Builds
    the same domain models the pipeline would, then indexes for retrieval.
    """
    layer = session.layer
    entities = [
        _demo_entity(EntityType.REGION, "Germany"),
        _demo_entity(EntityType.ORGANIZATION, "Acme Corp"),
        _demo_entity(EntityType.PERSON, "Legal"),
    ]
    artifacts = [
        _demo_artifact(
            ArtifactType.CAMPAIGN_STATE,
            "Germany healthcare outbound",
            "Outbound is PAUSED pending Legal approval of updated compliance messaging.",
            {"status": "paused", "blocker": "legal compliance review"},
            ["Germany", "Legal"],
        ),
        _demo_artifact(
            ArtifactType.PRICING_POLICY,
            "EMEA healthcare pricing",
            "Standard EMEA healthcare discount capped at 15% without VP sign-off.",
            {"region": "EMEA", "max_discount": "15%"},
            ["Germany"],
        ),
        _demo_artifact(
            ArtifactType.ACCOUNT_INTELLIGENCE,
            "Acme Corp account",
            "Acme Corp is an expansion target in the healthcare vertical.",
            {"vertical": "healthcare", "stage": "expansion"},
            ["Acme Corp"],
        ),
    ]
    for entity in entities:
        await layer.graph_store.upsert_entity(entity)
    for artifact in artifacts:
        await layer.artifact_store.put(artifact)
        await layer.retrieval.index_artifact(artifact)
    return len(artifacts)


__all__ = ["CairnSession", "build_session", "seed_demo"]
