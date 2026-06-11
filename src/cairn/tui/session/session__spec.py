from cairn.tui.session import LLMChoice, SessionConfig, build_session, seed_demo
from cairn.tui.session.session__consts import MOCK_LABEL


async def test_build_session_defaults_to_offline_mock() -> None:
    session = build_session(SessionConfig(llm=LLMChoice.MOCK))
    assert session.llm_label == MOCK_LABEL
    assert session.token_budget > 0
    artifacts, entities = await session.snapshot()
    assert artifacts == []
    assert entities == []


async def test_seed_demo_populates_and_is_queryable() -> None:
    session = build_session(SessionConfig(llm=LLMChoice.MOCK))
    count = await seed_demo(session)
    assert count == 3

    artifacts, entities = await session.snapshot()
    assert {a.title for a in artifacts} == {
        "Germany healthcare outbound",
        "EMEA healthcare pricing",
        "Acme Corp account",
    }
    assert {e.name for e in entities} == {"Germany", "Acme Corp", "Legal"}

    # The seeded artifacts are indexed, so the real retrieval/assembly read path
    # returns context even under the offline MockLLM.
    ctx = await session.layer.query("Germany healthcare outbound", token_budget=2000)
    assert "Germany" in ctx.render()

    # entity_refs hold graph entity ids (not names), so /wiki resolves every
    # seeded entity to a page instead of silently skipping them all.
    pages = await session.layer.refresh_wiki()
    assert len(pages) == 3
