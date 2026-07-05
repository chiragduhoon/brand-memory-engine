"""
FastAPI backend for चित्रगुप्त (Chitragupt) - the brand memory engine.
"""

import os
import shutil
import sys
import tempfile

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ingestion
import retrieval
import critique
import scoring

app = FastAPI(title="चित्रगुप्त (Chitragupt)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        result = ingestion.ingest_pdf(tmp_path, source_name=file.filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/query")
async def query(request: QueryRequest):
    try:
        context = retrieval.build_context(request.query)
        loop_result = critique.run_critique_loop(request.query, context, max_iterations=2)

        final_answer = loop_result["final_answer"]
        critique_log = loop_result["critique_log"]

        citation = scoring.citation_score(final_answer, context)
        trust = scoring.compute_trust_score(citation, critique_log)

        return {
            "final_answer": final_answer,
            "trust_score": trust,
            "critique_log": critique_log,
            "context_used": context,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
