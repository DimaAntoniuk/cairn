"""End-to-end demo using the MockLLM (no API key required).

Run:
    python examples/end_to_end.py
"""

import asyncio

from cairn import KnowledgeLayer
from cairn.domain import ArtifactType
from cairn.infra.llm import MockLLM
from cairn.ingestion import ManualConnector


def make_mock() -> MockLLM:
    return MockLLM(
        structured_responses={
            "expert information extractor": {
                "entities": [
                    {
                        "name": "Acme",
                        "entity_type": "organization",
                        "aliases": ["Acme Corporation"],
                        "confidence": 0.92,
                        "quote": "Acme",
                    },
                    {
                        "name": "EMEA Healthcare Pricing",
                        "entity_type": "policy",
                        "confidence": 0.85,
                    },
                ]
            },
            "relationship extractor": {
                "relationships": [
                    {
                        "source": "EMEA Healthcare Pricing",
                        "target": "Acme",
                        "relationship_type": "applies_to",
                        "confidence": 0.8,
                    }
                ]
            },
            "state/decision/constraint extractor": {
                "claims": [
                    {
                        "subject": "EMEA Healthcare Pricing",
                        "kind": "decision",
                        "statement": "Healthcare pricing for Acme in EMEA is held at last-quarter levels pending legal review.",
                        "confidence": 0.9,
                    }
                ]
            },
            "knowledge artifact compiler": {
                "title": "EMEA Healthcare Pricing — Acme",
                "summary": "Pricing held at last-quarter levels pending legal review.",
                "content": {
                    "current_state": "held",
                    "decisions": ["Hold pricing at last-quarter levels"],
                    "constraints": ["legal review pending"],
                    "risks": [],
                    "open_questions": ["When does legal expect to clear the messaging?"],
                },
                "confidence": 0.88,
                "conflicts": [],
            },
        },
    )


async def main() -> None:
    layer = KnowledgeLayer(llm=make_mock())

    docs = [
        "Pricing for Acme Corporation in EMEA Healthcare is held at "
        "last-quarter levels until legal clears the new compliance messaging.",
    ]
    await layer.ingest_from([ManualConnector.from_texts(docs)])
    result = await layer.process_buffer(artifact_type=ArtifactType.PRICING_POLICY)

    print(f"Ingested {result.documents} doc(s)")
    print(f"Extracted {len(result.facts)} fact(s)")
    print(f"Resolved {len(result.entities)} entit(ies)")
    print(f"Compiled {len(result.artifacts)} artifact(s)\n")

    ctx = await layer.query(
        "What is the current pricing posture for Acme in EMEA Healthcare?",
        entity_hints=["Acme", "EMEA Healthcare Pricing"],
        artifact_types=[ArtifactType.PRICING_POLICY],
        token_budget=2000,
    )
    print("=== Assembled context ===")
    print(ctx.render())
    print(f"\n[{ctx.total_tokens} tokens, {len(ctx.dropped_fragment_ids)} dropped]")


if __name__ == "__main__":
    asyncio.run(main())
