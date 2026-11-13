from scoring import citation_score, compute_trust_score

CTX = {"rules": [{"chunk_id": "chunk_r1"}], "facts": [{"chunk_id": "chunk_f1"}, {"chunk_id": "chunk_f2"}]}


def test_all_sentences_cited():
    ans = "The GPU has 24GB of memory [chunk_f1]. Always say GeForce, never Geforce [chunk_r1]."
    assert citation_score(ans, CTX) == 1.0


def test_partial_and_invalid_citations():
    ans = "Fact one [chunk_f1]. Unsupported claim. Made-up source [chunk_zzz]."
    assert citation_score(ans, CTX) == round(1 / 3, 3)


def test_empty_answer_scores_zero():
    assert citation_score("", CTX) == 0.0


def _log(iteration, broke=False, made_up=False):
    return [{"iteration": iteration, "critic_verdict": {"broke_rule": broke, "made_up_claim": made_up}}]


def test_trust_score_rewards_first_pass_acceptance():
    assert compute_trust_score(1.0, _log(1))["trust_score"] == 100.0
    assert compute_trust_score(1.0, _log(2))["trust_score"] == 85.0
    assert compute_trust_score(1.0, _log(2, broke=True))["trust_score"] == 65.0


def test_trust_score_without_critique_and_breakdown():
    out = compute_trust_score(0.5, [])
    assert out["trust_score"] == 25.0
    assert out["breakdown"] == {"citation_score": 0.5, "pass_rate": 0.0}
