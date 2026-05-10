from cairn.domain import SourceDocument
from cairn.extraction import LLMExtractor
from cairn.graph import GraphBuilder
from cairn.infra.llm import MockLLM
from cairn.infra.store import InMemoryGraphStore


async def test_graph_builder_resolves_relationships(
    mock_llm: MockLLM, germany_doc: SourceDocument
) -> None:
    extractor = LLMExtractor(mock_llm)
    facts = await extractor.extract(germany_doc)
    store = InMemoryGraphStore()
    builder = GraphBuilder(store, extractor=extractor)
    entities, n_rels = await builder.absorb(facts)
    assert len(entities) == 2
    assert n_rels == 1
    by_name = {e.name: e for e in entities}
    rels = await store.relationships_of(by_name["Germany Healthcare Outbound"].id, direction="out")
    assert len(rels) == 1
    assert rels[0].target_entity_id == by_name["Legal"].id
