"""
Trust scoring: how well-cited is the final answer, and how many critique
iterations did it take to get an accepted (or best-effort) answer.
"""

import re


def citation_score(final_answer, context):
    """
    Fraction of claim-sentences in the final answer that cite a valid
    chunk_id actually present in the retrieved context.
    """
    valid_ids = {r["chunk_id"] for r in context.get("rules", [])}
    valid_ids |= {f["chunk_id"] for f in context.get("facts", [])}

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", final_answer) if s.strip()]
    if not sentences:
        return 0.0

    cited = 0
    for sentence in sentences:
        found_ids = re.findall(r"\[(chunk_[a-zA-Z0-9_]+)\]", sentence)
        if found_ids and any(fid in valid_ids for fid in found_ids):
            cited += 1

    return round(cited / len(sentences), 3)


def compute_trust_score(citation_score_value, critique_log):
    """
    pass_rate reflects which iteration the critic accepted the answer on:
    - accepted on iteration 1 -> high pass rate
    - accepted on iteration 2 -> medium pass rate
    - never accepted (hit max_iterations with violations still flagged) -> low
    """
    if not critique_log:
        pass_rate = 0.0
    else:
        last = critique_log[-1]
        verdict = last["critic_verdict"]
        violation = verdict.get("broke_rule") or verdict.get("made_up_claim")
        iteration = last["iteration"]

        if not violation and iteration == 1:
            pass_rate = 1.0
        elif not violation and iteration > 1:
            pass_rate = 0.7
        else:
            pass_rate = 0.3

    composite = round((citation_score_value * 0.5 + pass_rate * 0.5) * 100, 1)

    return {
        "trust_score": composite,
        "breakdown": {
            "citation_score": citation_score_value,
            "pass_rate": pass_rate,
        },
    }
