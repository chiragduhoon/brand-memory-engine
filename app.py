"""
Streamlit UI for चित्रगुप्त (Chitragupt). Calls the FastAPI backend over HTTP.
"""

import html
import re

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="चित्रगुप्त — Chitragupt",
    page_icon="📜",
    layout="wide",
)

# ---------------------------------------------------------------- styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&family=Noto+Serif+Devanagari:wght@600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.hero {
  padding: 1.6rem 2rem 1.4rem 2rem;
  border-radius: 16px;
  background: linear-gradient(135deg, #161b26 0%, #1d1420 55%, #2a1218 100%);
  border: 1px solid #2b3040;
  margin-bottom: 1.2rem;
}
.hero .dev {
  font-family: 'Noto Serif Devanagari', serif;
  font-size: 2.6rem; font-weight: 600; line-height: 1.15;
  background: linear-gradient(90deg, #f5f2ec, #e63946);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero .sub { color: #9aa3b5; font-size: .95rem; margin-top: .3rem; }
.pipeline { margin-top: 1rem; display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; }
.pipe-step {
  font-size: .72rem; letter-spacing: .04em; font-weight: 600;
  color: #c9d2e3; background: #212838; border: 1px solid #323b52;
  padding: .25rem .6rem; border-radius: 999px; white-space: nowrap;
}
.pipe-arrow { color: #566080; font-size: .8rem; }

.answer-card {
  background: #161b26; border: 1px solid #2b3040; border-left: 4px solid #e63946;
  border-radius: 12px; padding: 1.3rem 1.5rem; line-height: 1.75; font-size: 1.02rem;
}
.cite {
  display: inline-block; font-size: .72rem; font-weight: 600;
  color: #ffd166; background: #2a2413; border: 1px solid #4d431f;
  padding: .05rem .5rem; border-radius: 999px; margin: 0 .15rem;
  vertical-align: baseline;
}

.score-num { font-family: 'Fraunces', serif; font-size: 3rem; font-weight: 700; line-height: 1; }
.score-label { color: #9aa3b5; font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; }
.bar-track { background: #212838; border-radius: 999px; height: 10px; width: 100%; margin-top: .45rem; }
.bar-fill { height: 10px; border-radius: 999px; }

.iter-card {
  background: #161b26; border: 1px solid #2b3040; border-radius: 12px;
  padding: 1rem 1.2rem; margin-bottom: .8rem;
}
.badge-pass, .badge-fail {
  font-size: .72rem; font-weight: 700; letter-spacing: .05em;
  padding: .2rem .6rem; border-radius: 999px;
}
.badge-pass { color: #7ee2a8; background: #12291c; border: 1px solid #1f4a31; }
.badge-fail { color: #ff8f9a; background: #2c1418; border: 1px solid #57232b; }

.chunk-card {
  background: #12161f; border: 1px solid #262d3d; border-radius: 10px;
  padding: .8rem 1rem; margin-bottom: .6rem; font-size: .88rem; color: #c4cbda;
}
.tag-pill {
  font-size: .68rem; font-weight: 600; color: #9ecbff;
  background: #14243a; border: 1px solid #24405f;
  padding: .12rem .5rem; border-radius: 999px; margin-right: .4rem;
}
.src-pill { font-size: .68rem; color: #8a93a8; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- helpers
def render_citations(text):
    """Escape model output, then swap [chunk_N] markers for styled pills."""
    safe = html.escape(text)
    safe = re.sub(r"\[(chunk_[a-zA-Z0-9_]+)\]", r'<span class="cite">\1</span>', safe)
    return safe.replace("\n", "<br>")


def score_bar(label, value, color):
    pct = max(0.0, min(1.0, float(value))) * 100
    st.markdown(f"""
    <div style="margin-bottom:.9rem;">
      <div style="display:flex;justify-content:space-between;">
        <span class="score-label">{label}</span>
        <span style="font-weight:600;color:{color};">{value:.2f}</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color};"></div></div>
    </div>
    """, unsafe_allow_html=True)


def friendly_error(text):
    if "429" in text or "rate limit" in text.lower():
        return ("Rate limit hit on the LLM providers. Wait ~60 seconds and try once more — "
                "one query at a time keeps things inside the free-tier window.")
    return text


# ---------------------------------------------------------------- header
st.markdown("""
<div class="hero">
  <div class="dev">चित्रगुप्त</div>
  <div class="sub">In the tradition of <b>Chitragupta</b>, the divine record-keeper who inscribes every deed
  and judges each one — this engine logs every retrieval, judges every draft, and enforces every rule
  before an answer may leave the ledger.</div>
  <div class="sub" style="margin-top:.35rem;font-style:italic;color:#7d8699;">
  हर उत्तर दर्ज है · हर नियम लागू है — every answer recorded, every rule enforced.</div>
  <div class="pipeline">
    <span class="pipe-step">📄 INGEST</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">🏷️ CLASSIFY + QUARANTINE</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">🗂️ RULES ∥ FACTS</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">🔍 RECALL + TOP-K</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">✍️ DRAFT</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">⚖️ CRITIQUE ×2</span><span class="pipe-arrow">→</span>
    <span class="pipe-step">🛡️ TRUST SCORE</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 📜 अभिलेख · Inscribe a document")
    st.caption("The PDF is chunked and every chunk is judged before entering the records: **rule**, **fact**, or **suspicious** — deceitful passages are cast out to the quarantine log, never embedded.")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    if uploaded_file is not None and st.button("Ingest", use_container_width=True, type="primary"):
        with st.spinner("Classifying chunks… (one LLM call per chunk)"):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                resp = requests.post(f"{API_BASE}/ingest", files=files, timeout=600)
                if resp.ok:
                    r = resp.json()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Rules", r.get("rules_stored", 0))
                    c2.metric("Facts", r.get("facts_stored", 0))
                    c3.metric("Flagged", r.get("suspicious_flagged", 0))
                    st.success(f"Ingested {r.get('total_chunks', 0)} chunks from {uploaded_file.name}")
                else:
                    st.error(friendly_error(resp.text))
            except requests.RequestException as e:
                st.error(f"Could not reach backend: {e}")

    st.divider()
    st.markdown("### ⚖️ न्याय · How it judges")
    st.caption(
        "**Rules** (धर्म) are retrieved with a recall guarantee — tag match returns "
        "ALL applicable rules, and they are never truncated from context.\n\n"
        "**Facts** use top-k similarity and absorb any token-budget cuts.\n\n"
        "A second LLM — the record-keeper's court — judges every draft for rule "
        "violations and invented claims before you see it. Max 2 hearings, every "
        "verdict inscribed in the ledger below."
    )

# ---------------------------------------------------------------- query
if "history" not in st.session_state:
    st.session_state.history = []

with st.form("query_form", clear_on_submit=False):
    col_in, col_btn = st.columns([5, 1])
    query = col_in.text_input(
        "Ask the record-keeper",
        placeholder="Ask the record-keeper… e.g. What rules must I follow when using the logo?",
        label_visibility="collapsed",
    )
    submitted = col_btn.form_submit_button("पूछो ⚖️", use_container_width=True, type="primary")

if submitted and query.strip():
    with st.spinner("Retrieving → drafting → critiquing → scoring…"):
        try:
            resp = requests.post(f"{API_BASE}/query", json={"query": query}, timeout=300)
            if resp.ok:
                st.session_state.history.insert(0, {"query": query, "data": resp.json()})
            else:
                st.error(friendly_error(resp.text))
        except requests.RequestException as e:
            st.error(f"Could not reach backend: {e}")

# ---------------------------------------------------------------- results
for idx, item in enumerate(st.session_state.history):
    data = item["data"]
    trust = data["trust_score"]
    log = data["critique_log"]
    ctx = data["context_used"]
    composite = trust["trust_score"]
    cit = trust["breakdown"]["citation_score"]
    pr = trust["breakdown"]["pass_rate"]
    tcolor = "#7ee2a8" if composite >= 75 else ("#ffd166" if composite >= 45 else "#ff8f9a")

    container = st.container() if idx == 0 else st.expander(f"🕘 {item['query']}", expanded=False)
    with container:
        if idx == 0:
            st.markdown(f"#### ❓ {item['query']}")

        col_a, col_s = st.columns([2.4, 1])

        with col_a:
            st.markdown(
                f'<div class="answer-card">{render_citations(data["final_answer"])}</div>',
                unsafe_allow_html=True,
            )

        with col_s:
            st.markdown(f"""
            <div style="text-align:center;padding:.4rem 0 1rem 0;">
              <div class="score-num" style="color:{tcolor};">{composite:.0f}</div>
              <div class="score-label">Trust Score / 100</div>
              <div style="font-size:.72rem;color:#7d8699;font-style:italic;margin-top:.2rem;">बही में दर्ज · as inscribed in the ledger</div>
            </div>
            """, unsafe_allow_html=True)
            score_bar("Citation coverage", cit, "#9ecbff")
            score_bar("Critic pass rate", pr, "#e63946")
            st.caption(f"Accepted after {len(log)} iteration(s) · {ctx['total_tokens']} context tokens")

        with st.expander(f"📖 कर्म लेखा · Ledger of deeds — {len(log)} draft(s) judged"):
            for entry in log:
                v = entry["critic_verdict"]
                failed = v.get("broke_rule") or v.get("made_up_claim")
                badge = ('<span class="badge-fail">✗ अधर्म · FLAGGED</span>' if failed
                         else '<span class="badge-pass">✓ धर्म · APPROVED</span>')
                st.markdown(f"""
                <div class="iter-card">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
                    <strong>Draft {entry['iteration']}</strong>{badge}
                  </div>
                  <div style="color:#c4cbda;font-size:.92rem;line-height:1.6;">{render_citations(entry['draft'])}</div>
                  <div style="margin-top:.7rem;padding-top:.6rem;border-top:1px solid #262d3d;font-size:.85rem;color:#9aa3b5;">
                    <strong style="color:#c9d2e3;">⚖️ The record-keeper's verdict:</strong> {html.escape(v.get('verdict_reasoning', ''))}
                    {'<br><strong style="color:#ff8f9a;">Rule broken:</strong> ' + html.escape(str(v.get('which_rule_chunk_id'))) if v.get('broke_rule') else ''}
                    {'<br><strong style="color:#ff8f9a;">Unsupported:</strong> ' + html.escape('; '.join(v.get('unsupported_claims', []))) if v.get('made_up_claim') else ''}
                  </div>
                </div>
                """, unsafe_allow_html=True)

        with st.expander(f"🗂️ प्रमाण · Evidence retrieved — {len(ctx['rules'])} rule(s), {len(ctx['facts'])} fact(s)"):
            col_r, col_f = st.columns(2)
            with col_r:
                st.markdown("**⚖️ Rules (धर्म)** · guaranteed recall, never truncated")
                for r in ctx["rules"]:
                    match = r.get("match_type", "tag")
                    st.markdown(f"""
                    <div class="chunk-card">
                      <div style="margin-bottom:.4rem;">
                        <span class="cite">{r['chunk_id']}</span>
                        <span class="tag-pill">{html.escape(str(r.get('category_tag')))}</span>
                        <span class="src-pill">{'🎯 tag match' if match == 'tag' else '📐 similarity fallback'}</span>
                      </div>
                      {html.escape(r['text'][:400])}{'…' if len(r['text']) > 400 else ''}
                    </div>
                    """, unsafe_allow_html=True)
            with col_f:
                st.markdown("**📊 Facts** · top-k similarity")
                if not ctx["facts"]:
                    st.caption("No facts made it into the budget for this query.")
                for f in ctx["facts"]:
                    st.markdown(f"""
                    <div class="chunk-card">
                      <div style="margin-bottom:.4rem;">
                        <span class="cite">{f['chunk_id']}</span>
                        <span class="tag-pill">{html.escape(str(f.get('category_tag')))}</span>
                        <span class="src-pill">{html.escape(str(f.get('source')))}</span>
                      </div>
                      {html.escape(f['text'][:400])}{'…' if len(f['text']) > 400 else ''}
                    </div>
                    """, unsafe_allow_html=True)

if not st.session_state.history:
    st.info("The ledger awaits. Inscribe a brand PDF from the sidebar (already done if the database is loaded), "
            "then ask the record-keeper a question above. "
            "Try: *“What rules must I follow when using the logo?”*")

st.markdown("""
<div style="text-align:center;margin-top:2.5rem;padding-top:1rem;border-top:1px solid #222839;
            color:#5d6579;font-size:.78rem;font-style:italic;">
जो लिखा गया है, वही कहा जाएगा — only what is written shall be spoken.<br>
<span style="font-style:normal;">चित्रगुप्त · zero-hallucination brand memory · every verdict auditable</span>
</div>
""", unsafe_allow_html=True)
