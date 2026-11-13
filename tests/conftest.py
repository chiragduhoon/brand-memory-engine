"""Tests run offline: no API keys, no real Chroma data.

storage.py opens ./storage/chroma_db on import, so switch to a throwaway directory first.
"""
import os
import tempfile

os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("CEREBRAS_API_KEY", "test")


def pytest_sessionstart(session):
    # Runs after pytest has resolved test paths but before test modules (and storage.py) are imported.
    os.chdir(tempfile.mkdtemp(prefix="chitragupt-tests-"))


class FakeCollection:
    """Minimal stand-in for a Chroma collection: get() returns everything, query() returns the first n."""

    def __init__(self, items):
        self.items = items  # list of (id, text, metadata)

    def get(self):
        return {"ids": [i for i, _, _ in self.items], "documents": [d for _, d, _ in self.items],
                "metadatas": [m for _, _, m in self.items]}

    def query(self, query_texts, n_results):
        top = self.items[:n_results]
        return {"ids": [[i for i, _, _ in top]], "documents": [[d for _, d, _ in top]],
                "metadatas": [[m for _, _, m in top]], "distances": [[0.1 * k for k in range(len(top))]]}
