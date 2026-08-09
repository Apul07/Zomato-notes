"""
ai_service.py
Part 3 — reusable AI service function + the auto-tagging prompt template.

Two modes:
  - MOCK_AI=1 (or --mock): deterministic, offline, rule-based canned
    response. No API key, no signup, no internet required. THIS IS THE
    GRADED, DEFAULT BASELINE.
  - MOCK_AI=0 with GROQ_API_KEY set: optional real path against Groq's
    free-tier chat completion API (OpenAI-compatible schema).
"""
import json
import logging
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ai_service")

# ---------------------------------------------------------------------------
# The five-part prompt template (Instructions, Context, Input, Constraints,
# Output Format). Kept verbatim / in one place so the repo can point to it.
# ---------------------------------------------------------------------------
AUTO_TAG_PROMPT_TEMPLATE = """\
### Instructions
You are an assistant that reads a short personal/work note and produces a \
structured auto-tagging suggestion for it. Read the note content given \
below and generate concise tags and a one-sentence summary.

### Context
This note was just created inside "Zomato Notes", an internal knowledge \
base used by on-call support engineers to capture and later retrieve \
short notes during and after incidents. Good tags and summaries help \
engineers scan and retrieve notes quickly under time pressure.

### Input
Note content:
\"\"\"
{note_content}
\"\"\"

### Constraints
- Return 1 to 3 short, lowercase, single- or two-word keyword strings as "tags".
- Return exactly one sentence, at most 20 words, as "summary".
- No text may surround the JSON object. Do not use markdown code fences.
- Do not include any keys other than "tags" and "summary".

### Output Format
Return only a JSON object with exactly two keys:
{{"tags": ["...", "..."], "summary": "..."}}
"""


def _mock_response(note_content: str) -> str:
    """
    Deterministic, offline, rule-based canned response. Used whenever
    MOCK_AI=1 (or the --mock flag is passed). No network call is made.
    """
    words = re.findall(r"[A-Za-z']+", note_content)
    significant = [w for w in words if len(w) > 3]
    tags_source = significant if len(significant) >= 3 else words
    tags = [w.lower() for w in tags_source[:3]] or ["note"]

    sentences = re.split(r"(?<=[.!?])\s+", note_content.strip())
    first_sentence = sentences[0] if sentences else note_content
    summary_words = first_sentence.split()[:20]
    summary = " ".join(summary_words)
    if not summary.endswith((".", "!", "?")):
        summary += "."

    return json.dumps({"tags": tags, "summary": summary})


def _is_mock_mode() -> bool:
    if os.getenv("MOCK_AI", "1") == "1":
        return True
    return "--mock" in sys.argv


def get_ai_response(user_message: str, system_prompt: str) -> str:
    """
    Sends a chat-completion request using the standard system / user /
    assistant message-role format and returns the text reply.

    In mock mode (default, MOCK_AI=1) this never touches the network and
    never raises for a missing API key.
    """
    if _is_mock_mode():
        # In mock mode we treat `user_message` as the raw note content and
        # fabricate a deterministic reply — no network call, no key needed.
        return _mock_response(user_message)

    # --- Optional real path: Groq's free-tier OpenAI-compatible API ---
    import requests

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set; falling back to mock response.")
        return _mock_response(user_message)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def build_auto_tag_prompt(note_content: str) -> str:
    return AUTO_TAG_PROMPT_TEMPLATE.format(note_content=note_content)


def get_ai_suggestion(note_content: str) -> dict | None:
    """
    Calls get_ai_response with the auto-tag prompt, parses the JSON reply,
    and returns {"tags": [...], "summary": "..."} or None on any failure.
    Never raises — parse failures are caught and logged.
    """
    prompt = build_auto_tag_prompt(note_content)
    try:
        raw = get_ai_response(user_message=note_content, system_prompt=prompt)
        parsed = json.loads(raw)
        if (
            isinstance(parsed, dict)
            and "tags" in parsed
            and "summary" in parsed
            and isinstance(parsed["tags"], list)
            and isinstance(parsed["summary"], str)
        ):
            return {"tags": parsed["tags"], "summary": parsed["summary"]}
        logger.error("AI response missing required keys: %r", raw)
        return None
    except Exception as exc:  # noqa: BLE001 - we deliberately never crash the caller
        logger.error("Failed to parse AI response for note: %s", exc)
        return None