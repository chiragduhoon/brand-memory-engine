"""
Draft -> critique -> redraft loop. The critic checks the draft against the
retrieved rules/facts for rule violations and unsupported (hallucinated)
claims, capped at 2 iterations.
"""

import json

import llm_client


def _format_context(context):
    rules_text = "\n".join(
        f"[{r['chunk_id']}] {r['text']}" for r in context.get("rules", [])
    ) or "(no rules retrieved)"
    facts_text = "\n".join(
        f"[{f['chunk_id']}] {f['text']}" for f in context.get("facts", [])
    ) or "(no facts retrieved)"
    return rules_text, facts_text


def draft_answer(query, context, critic_feedback=None):
    rules_text, facts_text = _format_context(context)

    feedback_block = ""
    if critic_feedback:
        feedback_block = f"""
Your previous draft was reviewed and found to have issues:
{json.dumps(critic_feedback, indent=2)}

Revise your answer to fix these issues.
"""

    prompt = f"""You are a brand assistant answering questions about a brand.

BRAND RULES (must be followed strictly, never violate these):
{rules_text}

BRAND FACTS (the only source of factual information you may use):
{facts_text}

RULES FOR YOUR ANSWER:
- Only use information from the BRAND FACTS and BRAND RULES above. Do not invent or assume anything not present there.
- For every factual claim you make, cite the chunk_id it came from inline, copying the id EXACTLY as shown in the brackets at the start of that fact or rule (e.g. "[chunk_3]").
- The ONLY valid chunk_ids are the bracketed ids shown above. Numbers appearing inside the text itself (page numbers, years, statistics) are NOT chunk_ids - never invent a citation from them.
- Follow every brand rule listed above without exception.
- If the facts don't contain enough information to answer, say so honestly instead of guessing.
{feedback_block}
Question: {query}

Answer:"""

    try:
        raw = llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        print(f"[critique] draft raw output: {raw}")
        return raw.strip()
    except Exception as e:
        raise RuntimeError(f"Draft call failed: {e}") from e


CRITIC_PROMPT = """You are a strict brand compliance critic. Review the DRAFT ANSWER against the BRAND RULES and BRAND FACTS below.

BRAND RULES:
{rules_text}

BRAND FACTS:
{facts_text}

DRAFT ANSWER:
\"\"\"{draft}\"\"\"

Check for:
1. Whether the draft violates any brand rule.
2. Whether the draft makes any claim not supported by the BRAND FACTS (a hallucination / made-up claim).

Respond with ONLY strict JSON in this exact shape, no other text:
{{"broke_rule": bool, "which_rule_chunk_id": "<chunk_id or null>", "made_up_claim": bool, "unsupported_claims": ["<claim text>", ...], "verdict_reasoning": "<one sentence>"}}
"""


def critique_draft(draft, context):
    rules_text, facts_text = _format_context(context)
    prompt = CRITIC_PROMPT.format(rules_text=rules_text, facts_text=facts_text, draft=draft)

    try:
        raw = llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            json_mode=True,
        )
        print(f"[critique] critic raw output: {raw}")
        return llm_client.parse_json_response(raw)
    except Exception as e:
        raise RuntimeError(f"Critique call failed: {e}") from e


def run_critique_loop(query, context, max_iterations=2):
    log = []
    final_answer = None
    critic_feedback = None

    for iteration in range(1, max_iterations + 1):
        draft = draft_answer(query, context, critic_feedback=critic_feedback)
        verdict = critique_draft(draft, context)

        log.append({
            "iteration": iteration,
            "draft": draft,
            "critic_verdict": verdict,
        })

        final_answer = draft

        violation = verdict.get("broke_rule") or verdict.get("made_up_claim")
        if not violation:
            break

        critic_feedback = verdict

    return {
        "final_answer": final_answer,
        "critique_log": log,
    }
