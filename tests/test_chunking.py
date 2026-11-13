from ingestion import chunk_text


def _para(words):
    return " ".join(["word"] * words)


def test_paragraphs_are_never_split():
    paras = [_para(100), _para(120), _para(90), _para(200)]
    chunks = chunk_text("\n\n".join(paras))
    rebuilt = [p for c in chunks for p in c.split("\n\n")]
    assert rebuilt == paras


def test_chunks_respect_max_unless_one_paragraph_is_bigger():
    paras = [_para(150)] * 6                     # ~195 tokens each
    for c in chunk_text("\n\n".join(paras), min_tokens=300, max_tokens=500):
        assert int(len(c.split()) * 1.3) <= 500


def test_short_text_is_one_chunk_and_blank_text_none():
    assert chunk_text("short paragraph") == ["short paragraph"]
    assert chunk_text("\n\n  \n\n") == []
