"""
Combines rule (guaranteed-recall) and fact (top-k) retrieval into a single
context object, enforcing a hard token budget.
"""

import storage

MAX_CONTEXT_TOKENS = 1500


def _token_estimate(s):
    return int(len(s.split()) * 1.3)


def build_context(query):
    facts = storage.query_facts(query, top_k=4)
    rules = storage.query_rules(query)

    rule_tokens = sum(_token_estimate(r["text"]) for r in rules)
    remaining_budget = max(MAX_CONTEXT_TOKENS - rule_tokens, 0)

    kept_facts = []
    used_tokens = 0
    for fact in facts:
        fact_tokens = _token_estimate(fact["text"])
        if used_tokens + fact_tokens > remaining_budget:
            break
        kept_facts.append(fact)
        used_tokens += fact_tokens

    total_tokens = rule_tokens + used_tokens

    return {
        "facts": kept_facts,
        "rules": rules,
        "total_tokens": total_tokens,
    }
