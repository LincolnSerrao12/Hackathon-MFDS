"""On-device privacy gate. NOTHING reaches the cloud LLM except through `prepare_payload` / `redact`.

Detection: Presidio (spaCy en_core_web_sm: names, emails, phones, cards, IBAN, IPs...) plus
India-specific regexes (PAN, Aadhaar, IFSC, UPI id, passport, account numbers) and secrets (API keys, passwords).
Redaction replaces each finding with a typed placeholder, e.g. <EMAIL_1>, so structure is kept but identity is not.
Paths are also redacted: the home-directory username and any PII in file names.
"""
import os
import re
from dataclasses import dataclass, field

_REGEX = {
    "IN_PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "IN_AADHAAR": r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b",
    "IN_IFSC": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "UPI_ID": r"\b[\w.\-]{2,}@(?:upi|ybl|okaxis|okhdfcbank|oksbi|okicici|paytm|ibl|axl)\b",
    "IN_PASSPORT": r"\b[A-PR-WYa-pr-wy][1-9]\d\s?\d{4}[1-9]\b",
    "BANK_ACCOUNT": r"(?i)\b(?:a/?c|acct?|account)(?:\s*(?:no|number|#))?[\s.:]*\d{9,18}\b",
    "SECRET": r"\b(?:sk-[A-Za-z0-9_\-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_\-]{30,}|xox[abpr]-[A-Za-z0-9\-]{10,})",
    # "<keyword> <separator> <value>": only the value (group v) is replaced, so "password: hunter2" -> "password: <SECRET_1>".
    # Separator is ':', '=', '-', 'is' / 'was', or plain space when the value looks like a secret (has a digit or symbol).
    "SECRET_KV": r"(?i)\b(?:password|passwd|passcode|passphrase|pass\s*word|pwd|pw|pass|pin|mpin|upi\s+pin|otp|"
                 r"api[_\s-]?key|secret(?:[_\s-]?key)?|access[_\s-]?key|private[_\s-]?key|(?:auth|access|bearer)?[_\s-]?token)"
                 r"(?:\s+(?:for|of|to)\s+[\w.@\-]+)?"
                 r"(?:\s*(?:[:=]|[-\u2013]|\bis\b|\bwas\b)\s*(?:\bis\b\s*)?|\s+(?=[^\s,;]*[\d@#$%^&*!?]))"
                 r"(?P<v>(?=[^\s,;]{3,})[^\s,;]*[^\s,;.!?)\]\"'])",
    "CARD": r"\b(?:\d[ -]?){13,19}\b",
    "PHONE": r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)|(?<!\d)\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\d)",
    "EMAIL": r"\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b",
}
_COMPILED = {k: re.compile(v) for k, v in _REGEX.items()}
_PRESIDIO_KEEP = {"PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "IP_ADDRESS", "US_SSN",
                  "US_PASSPORT", "UK_NHS", "MEDICAL_LICENSE", "CRYPTO", "LOCATION_PRECISE"}
_analyzer = None


def _get_analyzer():
    """Presidio engine on the small spaCy model; None if unavailable (regex-only fallback)."""
    global _analyzer
    if _analyzer is None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}).create_engine()
            _analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
        except Exception:
            _analyzer = False
    return _analyzer or None


@dataclass
class Finding:
    type: str
    start: int
    end: int
    score: float = 1.0


@dataclass
class Redaction:
    text: str
    findings: list = field(default_factory=list)

    @property
    def counts(self) -> dict:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.type] = out.get(f.type, 0) + 1
        return out


def detect(text: str, use_presidio: bool = True) -> list[Finding]:
    found: list[Finding] = []
    for typ, rx in _COMPILED.items():
        for m in rx.finditer(text):
            if typ == "CARD" and not _luhn(re.sub(r"\D", "", m.group())):
                continue
            start, end = m.span("v") if "v" in rx.groupindex else m.span()  # keyed secrets: redact the value only
            found.append(Finding("SECRET" if typ == "SECRET_KV" else typ, start, end))
    if use_presidio and (a := _get_analyzer()) and text.strip():
        for r in a.analyze(text=text[:100_000], language="en", entities=sorted(_PRESIDIO_KEEP)):
            if r.score >= 0.4:
                found.append(Finding({"EMAIL_ADDRESS": "EMAIL", "PHONE_NUMBER": "PHONE", "CREDIT_CARD": "CARD"}.get(r.entity_type, r.entity_type), r.start, r.end, r.score))
    return _merge(found)


def _merge(fs: list[Finding]) -> list[Finding]:
    fs = sorted(fs, key=lambda f: (f.start, -(f.end - f.start)))
    out: list[Finding] = []
    for f in fs:
        if out and f.start < out[-1].end:  # overlap: keep the longer span
            if f.end > out[-1].end and (f.end - f.start) > (out[-1].end - out[-1].start):
                out[-1] = f
            continue
        out.append(f)
    return out


def _luhn(num: str) -> bool:
    if not 13 <= len(num) <= 19:
        return False
    s, alt = 0, False
    for ch in reversed(num):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        s += d
        alt = not alt
    return s % 10 == 0


def redact(text: str, use_presidio: bool = True) -> Redaction:
    """Replace PII with typed placeholders. Same value -> same placeholder within one call."""
    findings = detect(text, use_presidio)
    seen: dict[tuple, str] = {}
    counters: dict[str, int] = {}
    out, pos = [], 0
    for f in findings:
        raw = text[f.start : f.end]
        key = (f.type, raw.lower())
        if key not in seen:
            counters[f.type] = counters.get(f.type, 0) + 1
            seen[key] = f"<{f.type}_{counters[f.type]}>"
        out.append(text[pos : f.start])
        out.append(seen[key])
        pos = f.end
    out.append(text[pos:])
    return Redaction("".join(out), findings)


def redact_path(path: str, use_presidio: bool = False) -> Redaction:
    """Redact a file path: swap the home dir for ~ and strip PII from the remaining parts (regex only by default)."""
    home = os.path.expanduser("~")
    p = path.replace(home, "~", 1) if path.startswith(home) else path
    return redact(p, use_presidio)


def prepare_payload(items: list[dict], max_snippet: int = 200) -> dict:
    """Build the exact object that may be sent to a cloud LLM from file records, plus a report.
    Only non-sensitive metadata leaves: redacted relative path, kind, ext, size bucket, year. Snippets are
    redacted and truncated. The returned dict is also shown to the user in the UI ("what was sent")."""
    clean, counts = [], {}
    for it in items:
        r = redact_path(it.get("path", ""))
        n = redact(os.path.basename(it.get("name", "")), use_presidio=False)
        rec = {"path": r.text, "name": n.text, "kind": it.get("kind"), "ext": it.get("ext"),
               "size_kb": round((it.get("size") or 0) / 1024), "year": (it.get("modified") or "")[:4]}
        if it.get("snippet"):
            s = redact(re.sub(r"</?mark>", "", it["snippet"])[:max_snippet])
            rec["snippet"] = s.text
            for k, v in s.counts.items():
                counts[k] = counts.get(k, 0) + v
        for k, v in {**r.counts, **n.counts}.items():
            counts[k] = counts.get(k, 0) + v
        clean.append(rec)
    return {"items": clean, "redacted": counts, "note": "Raw file contents, usernames and personal identifiers never leave this device."}
