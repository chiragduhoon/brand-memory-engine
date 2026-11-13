"""The README's key claim: every rule whose tag matches the query is returned, never trimmed by top-k or the token budget."""
import retrieval
import storage
from conftest import FakeCollection

RULES = [
    ("chunk_r1", "Never call the product cheap.", {"category_tag": "pricing_language", "source": "guide.pdf"}),
    ("chunk_r2", "Pricing must be shown in USD.", {"category_tag": "pricing_format", "source": "guide.pdf"}),
    ("chunk_r3", "Logo must not be stretched.", {"category_tag": "logo_prohibition", "source": "guide.pdf"}),
    ("chunk_r4", "Use a confident, friendly tone.", {"category_tag": "tone_voice", "source": "guide.pdf"}),
]


def test_all_matching_rules_returned(monkeypatch):
    monkeypatch.setattr(storage, "rules_collection", FakeCollection(RULES))
    got = storage.query_rules("How should we talk about pricing?")
    assert {r["chunk_id"] for r in got} == {"chunk_r1", "chunk_r2"}
    assert all(r["match_type"] == "tag" for r in got)


def test_explicit_category_tags_are_added(monkeypatch):
    monkeypatch.setattr(storage, "rules_collection", FakeCollection(RULES))
    got = storage.query_rules("pricing question", category_tags=["logo_prohibition"])
    assert {r["chunk_id"] for r in got} == {"chunk_r1", "chunk_r2", "chunk_r3"}


def test_falls_back_to_similarity_when_no_tag_matches(monkeypatch):
    monkeypatch.setattr(storage, "rules_collection", FakeCollection(RULES))
    got = storage.query_rules("What is the warranty period?")
    assert len(got) == 3 and all(r["match_type"] == "similarity_fallback" for r in got)


def test_rules_never_trimmed_facts_fill_remaining_budget(monkeypatch):
    big_rule = ("chunk_rbig", " ".join(["rule"] * 1000), {"category_tag": "pricing_language"})   # ~1300 tokens
    facts = [(f"chunk_f{i}", " ".join(["fact"] * 100), {"category_tag": "spec"}) for i in range(4)]  # ~130 each
    monkeypatch.setattr(storage, "rules_collection", FakeCollection([big_rule]))
    monkeypatch.setattr(storage, "facts_collection", FakeCollection(facts))
    ctx = retrieval.build_context("pricing")
    assert [r["chunk_id"] for r in ctx["rules"]] == ["chunk_rbig"]
    assert len(ctx["facts"]) == 1                     # only ~200 tokens of budget left after the rule
    assert ctx["total_tokens"] <= retrieval.MAX_CONTEXT_TOKENS
