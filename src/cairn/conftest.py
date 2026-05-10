import pytest

from cairn.domain import SourceDocument, SourceRef, SourceSystem
from cairn.infra.llm import MockLLM


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def germany_doc() -> SourceDocument:
    return SourceDocument(
        ref=SourceRef(system=SourceSystem.MANUAL, external_id="germany-1"),
        title="Germany healthcare update",
        content=(
            "We should pause healthcare outbound in Germany until legal "
            "approves updated compliance messaging."
        ),
    )


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM(
        structured_responses={
            "expert information extractor": {
                "entities": [
                    {
                        "name": "Germany Healthcare Outbound",
                        "entity_type": "campaign",
                        "aliases": [],
                        "confidence": 0.9,
                        "quote": "pause healthcare outbound in Germany",
                    },
                    {
                        "name": "Legal",
                        "entity_type": "organization",
                        "aliases": [],
                        "confidence": 0.8,
                    },
                ]
            },
            "relationship extractor": {
                "relationships": [
                    {
                        "source": "Germany Healthcare Outbound",
                        "target": "Legal",
                        "relationship_type": "depends_on",
                        "confidence": 0.85,
                    }
                ]
            },
            "state/decision/constraint extractor": {
                "claims": [
                    {
                        "subject": "Germany Healthcare Outbound",
                        "kind": "decision",
                        "statement": "Pause healthcare outbound in Germany pending legal approval.",
                        "reason": "compliance messaging not yet approved",
                        "confidence": 0.9,
                    }
                ]
            },
            "knowledge artifact compiler": {
                "title": "Germany Healthcare Outbound — Status",
                "summary": "Healthcare outbound in Germany is paused pending legal approval.",
                "content": {
                    "current_state": "paused",
                    "decisions": ["Pause outbound until legal approval"],
                    "constraints": ["compliance messaging not approved"],
                    "risks": [],
                    "open_questions": [],
                },
                "confidence": 0.88,
                "conflicts": [],
            },
        },
        default_chat="",
    )
