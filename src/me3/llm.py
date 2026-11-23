"""Cloud LLM client. Receives ONLY the payload built by privacy.prepare_payload (redacted metadata).
Without ANTHROPIC_API_KEY the app stays fully functional using on-device rule-based suggestions."""
import json
import os
import re

from . import db

GEMINI_MODEL = os.environ.get("ME3_GEMINI_MODEL", "gemini-3.5-flash-lite")
# tried in order when the chosen model is overloaded (503/429/timeout) or retired (404)
GEMINI_FALLBACKS = ["gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
CLAUDE_MODEL = os.environ.get("ME3_LLM_MODEL", "claude-haiku-5-5")

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


OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
OLLAMA_MODEL = os.environ.get("ME3_OLLAMA_MODEL", "gemma4:e4b")  # text + vision, fits an 8 GB GPU


def _ollama_ready() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            names = {m["name"] for m in json.load(r).get("models", [])}
        return OLLAMA_MODEL in names or f"{OLLAMA_MODEL}:latest" in names
    except Exception:  # noqa: BLE001
        return False


def provider() -> str | None:
    """Privacy first: the on-device Ollama model is the default. Cloud providers are used ONLY when
    ME3_LLM_PROVIDER=gemini|anthropic is set explicitly (and their key exists); there is no silent cloud fallback."""
    _load_env()
    want = os.environ.get("ME3_LLM_PROVIDER", "ollama").lower()
    if want == "gemini" and os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if want == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "ollama" if _ollama_ready() else None


def is_local() -> bool:
    return provider() == "ollama"


def available() -> bool:
    return provider() is not None


def model_name() -> str:
    return {"ollama": OLLAMA_MODEL, "gemini": GEMINI_MODEL}.get(provider() or "", CLAUDE_MODEL)


MODEL = CLAUDE_MODEL  # kept for backward compatibility


class LLMError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _gemini_call(model: str, payload: dict, body_override: dict | None = None) -> str:
    import urllib.error
    import urllib.request

    body = json.dumps(body_override or {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps({"files": payload["items"]})}]}],
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 4000},
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise LLMError(e.code, e.read().decode(errors="replace")[:300]) from e
    except (TimeoutError, urllib.error.URLError) as e:
        raise LLMError(504, f"{model} timed out") from e
    return "".join(p.get("text", "") for c in data.get("candidates", [])[:1]
                   for p in c.get("content", {}).get("parts", []))


def _gemini(payload: dict, body_override: dict | None = None) -> str:
    last: LLMError | None = None
    for model in [GEMINI_MODEL, *[m for m in GEMINI_FALLBACKS if m != GEMINI_MODEL]]:
        try:
            return _gemini_call(model, payload, body_override)
        except LLMError as e:
            if e.status in (401, 403):
                raise  # bad key: another model will not help
            last = e
    raise last  # type: ignore[misc]


def organise(payload: dict) -> dict:
    """Send the (already redacted) payload to the configured provider. Caller must have shown it to the user."""
    if provider() == "ollama":
        text = _ollama_chat([{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": json.dumps({"files": payload["items"]})}])
    elif provider() == "gemini":
        text = _gemini(payload)
    else:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=1500, system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps({"files": payload["items"]})}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group()) if m else {"summary": text, "suggestions": []}


def _ollama_chat(messages: list[dict], timeout: int = 180, num_predict: int = 1500) -> str:
    import urllib.error
    import urllib.request

    body = json.dumps({"model": OLLAMA_MODEL, "messages": messages, "stream": False, "think": False, "format": "json",
                       "keep_alive": "2m",
                       "options": {"temperature": 0.1, "num_predict": num_predict, "num_ctx": 8192}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)["message"]["content"]
    except urllib.error.HTTPError as e:
        raise LLMError(e.code, e.read().decode(errors="replace")[:300]) from e
    except (TimeoutError, urllib.error.URLError) as e:
        raise LLMError(504, f"Ollama did not answer: {e}") from e
