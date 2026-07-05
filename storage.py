"""
ChromaDB storage layer for the Brand Memory Engine.

Two separate collections on purpose:
- rules_collection: brand tone/style rules. Must be retrieved with GUARANTEED
  RECALL - a rule can matter to a query without being the closest embedding
  match, and missing one rule can mean a brand violation slips through.
- facts_collection: brand facts (specs, product info). Standard top-k
  similarity search is fine here - facts are ranked by relevance, not
  recall-critical.
"""

import chromadb

CHROMA_DIR = "./storage/chroma_db"

_client = chromadb.PersistentClient(path=CHROMA_DIR)

rules_collection = _client.get_or_create_collection("rules_collection")
facts_collection = _client.get_or_create_collection("facts_collection")

_COLLECTIONS = {
    "rules_collection": rules_collection,
    "facts_collection": facts_collection,
}


def add_chunks(chunks, collection_name):
    """
    chunks: list of dicts with keys: text, category_tag, source, chunk_id
    collection_name: "rules_collection" or "facts_collection"
    """
    collection = _COLLECTIONS[collection_name]
    if not chunks:
        return

    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[
            {
                "category_tag": c["category_tag"],
                "source": c["source"],
            }
            for c in chunks
        ],
    )


def query_facts(query_text, top_k=4):
    """Standard similarity search - facts are ranked by relevance."""
    results = facts_collection.query(query_texts=[query_text], n_results=top_k)
    return _format_results(results)


def query_rules(query_text, category_tags=None):
    """
    Rules need a recall guarantee, not a relevance ranking: a tone rule can be
    critical to a query even if it isn't the closest embedding match. So we
    first try tag matching (simple keyword overlap against stored
    category_tags) and return ALL rules under any matching tag. Only if no
    tag match is confident do we fall back to top-k similarity, purely so we
    still return something useful.
    """
    all_rules = rules_collection.get()
    all_ids = all_rules.get("ids", [])
    all_docs = all_rules.get("documents", [])
    all_metas = all_rules.get("metadatas", [])

    if all_ids:
        query_lower = query_text.lower()
        matched = []
        for _id, doc, meta in zip(all_ids, all_docs, all_metas):
            tag = (meta or {}).get("category_tag", "")
            tag_words = [w for w in tag.replace("_", " ").lower().split() if len(w) > 2]
            if tag_words and any(w in query_lower for w in tag_words):
                matched.append({
                    "chunk_id": _id,
                    "text": doc,
                    "category_tag": tag,
                    "source": (meta or {}).get("source"),
                    "match_type": "tag",
                })

        if category_tags:
            wanted = set(category_tags)
            for _id, doc, meta in zip(all_ids, all_docs, all_metas):
                tag = (meta or {}).get("category_tag", "")
                if tag in wanted and not any(m["chunk_id"] == _id for m in matched):
                    matched.append({
                        "chunk_id": _id,
                        "text": doc,
                        "category_tag": tag,
                        "source": (meta or {}).get("source"),
                        "match_type": "tag",
                    })

        if matched:
            return matched

    results = rules_collection.query(query_texts=[query_text], n_results=min(3, max(len(all_ids), 1)))
    formatted = _format_results(results)
    for r in formatted:
        r["match_type"] = "similarity_fallback"
    return formatted


def _format_results(results):
    formatted = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0] if results.get("distances") else [None] * len(ids)

    for _id, doc, meta, dist in zip(ids, docs, metas, dists):
        formatted.append({
            "chunk_id": _id,
            "text": doc,
            "category_tag": (meta or {}).get("category_tag"),
            "source": (meta or {}).get("source"),
            "similarity_score": dist,
        })
    return formatted
