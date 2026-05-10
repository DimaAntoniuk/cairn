from cairn.domain import SourceDocument
from cairn.extraction import LLMExtractor
from cairn.infra.llm import MockLLM


async def test_extractor_three_passes(mock_llm: MockLLM, germany_doc: SourceDocument) -> None:
    extractor = LLMExtractor(mock_llm)
    facts = await extractor.extract(germany_doc)
    kinds = {f.fact_type for f in facts}
    assert "entity" in kinds
    assert "relationship" in kinds
    assert "decision" in kinds
    assert all(f.source_ref == germany_doc.ref for f in facts)
