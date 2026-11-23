"""Cloud LLM client. Receives ONLY the payload built by privacy.prepare_payload (redacted metadata).
Without ANTHROPIC_API_KEY the app stays fully functional using on-device rule-based suggestions."""
import json
import os
import re

from . import db

MODEL = os.environ.get("ME3_LLM_MODEL", "claude-haiku-5-5")

SYSTEM = (
    "You are a file-organisation assistant. You receive a JSON list of files with redacted paths and metadata "
    "(placeholders like <EMAIL_1> hide personal data; never try to infer them). Propose a concise, practical folder "
    "structure and cleanup actions. Reply with ONLY JSON: "
    '{"summary": str, "suggestions": [{"title": str, "detail": str, "folder": str, "example_files": [str]}]} '
    "with at most 6 suggestions."
)


def _load_env():
    try:
        from dotenv import load_dotenv

        load_dotenv(db.ROOT / ".env")
    except Exception:
        pass


def available() -> bool:
    _load_env()
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def organise(payload: dict) -> dict:
    """Send the (already redacted) payload to Claude. Caller must have shown the payload to the user."""
    _load_env()
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=1500, system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps({"files": payload["items"]})}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group()) if m else {"summary": text, "suggestions": []}
