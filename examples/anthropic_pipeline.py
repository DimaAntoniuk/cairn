"""End-to-end demo using the real Anthropic API.

Requires:
    pip install 'cairn[anthropic]'
    export ANTHROPIC_API_KEY=...

Run:
    python examples/anthropic_pipeline.py
"""

from __future__ import annotations

import asyncio

from cairn import KnowledgeLayer
from cairn.ingestion import ManualConnector
from cairn.llm import AnthropicClient
from cairn.schemas import ArtifactType


SAMPLE_DOCS = [
    "We should pause healthcare outbound in Germany until legal approves "
    "updated compliance messaging. Edward to coordinate with the legal team.",
    "Acme Corporation expanded their contract by 30% last quarter; expansion "
    "strategy for Q3 should target adjacent business units.",
    "Pricing for the EMEA Scale tier is locked at £349/month through Q4. "
    "Channel partners receive a 20% commission on Scale and Organization tiers.",
]


async def main() -> None:
    layer = KnowledgeLayer(llm=AnthropicClient())

    await layer.ingest_from([ManualConnector.from_texts(SAMPLE_DOCS)])
    result = await layer.process_buffer(artifact_type=ArtifactType.ACCOUNT_INTELLIGENCE)
    print(result)

    ctx = await layer.query(
        "What is the current state of healthcare outbound in Germany?",
        entity_hints=["Germany"],
        token_budget=2000,
    )
    print("\n=== Assembled context ===")
    print(ctx.render())

    # Refresh the operational wiki and surface evaluation issues.
    pages = await layer.refresh_wiki()
    print(f"\nGenerated {len(pages)} wiki page(s).")

    issues = await layer.evaluate(check_contradictions=True)
    print(f"\nEvaluation surfaced {len(issues)} issue(s):")
    for issue in issues[:5]:
        print(f"  [{issue.kind.value}] severity={issue.severity:.2f} :: {issue.description}")


if __name__ == "__main__":
    asyncio.run(main())
