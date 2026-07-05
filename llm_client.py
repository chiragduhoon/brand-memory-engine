"""
Shared LLM call helper: tries Groq first, falls back to Cerebras (also
OpenAI-compatible, free tier) if Groq's rate limit is hit. Both ingestion.py
and critique.py go through this so the fallback only needs to be wired once.
"""

import json
import os
import time

import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"
CEREBRAS_MODEL = "gpt-oss-120b"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
# Cerebras free tier allows only 5 requests/minute (daily limits are large).
# A single query bursts 2-4 calls, so 429s here are transient - wait and retry.
CEREBRAS_MAX_RETRIES = 3
CEREBRAS_RETRY_WAIT_SECONDS = 20

_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _call_cerebras(messages, temperature, json_mode):
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise RuntimeError("CEREBRAS_API_KEY is not set. Add it to your .env file for fallback.")

    payload = {
        "model": CEREBRAS_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    for attempt in range(1, CEREBRAS_MAX_RETRIES + 1):
        response = requests.post(
            CEREBRAS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if response.status_code == 429 and attempt < CEREBRAS_MAX_RETRIES:
            wait = int(response.headers.get("retry-after", CEREBRAS_RETRY_WAIT_SECONDS))
            wait = min(max(wait, 1), 60)
            print(f"[llm_client] Cerebras per-minute limit hit, retrying in {wait}s "
                  f"(attempt {attempt}/{CEREBRAS_MAX_RETRIES})")
            time.sleep(wait)
            continue
        response.raise_for_status()
        content = response.json()["choices"][0]["message"].get("content")
        if not content:
            # gpt-oss models can return a reasoning-only message with no content
            raise RuntimeError("Cerebras returned an empty completion (no content field).")
        return content

    raise RuntimeError("Cerebras rate limit persisted across all retries.")


def parse_json_response(raw):
    """
    Tolerant JSON parse: models sometimes wrap JSON in markdown fences or
    prepend a sentence despite json_mode. Falls back to extracting the
    outermost {...} block before giving up.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(raw[start:end + 1])


def chat_completion(messages, temperature=0, json_mode=False):
    """
    Returns the raw text content of the completion. Tries Groq first; on ANY
    Groq failure (rate limit, outage, blocked model), falls back to Cerebras
    automatically - demo reliability over provider purity.
    """
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned an empty completion.")
        return content
    except Exception as e:
        print(f"[llm_client] Groq call failed, falling back to Cerebras: {e}")
        try:
            return _call_cerebras(messages, temperature, json_mode)
        except Exception as fallback_error:
            raise RuntimeError(
                f"Both Groq and Cerebras calls failed. Groq: {e} | Cerebras: {fallback_error}"
            ) from fallback_error
