"""Local natural-language query parser: pulls type / size / date filters out of plain English.
Runs fully on-device (no LLM needed). "fee receipt from last semester" -> text 'fee receipt' + date range."""
import re
from datetime import datetime, timedelta

KIND_WORDS = {
    "photo": "image", "photos": "image", "picture": "image", "pictures": "image", "image": "image",
    "images": "image", "pics": "image", "pic": "image", "screenshot": "image", "screenshots": "image",
    "video": "video", "videos": "video", "movie": "video", "movies": "video", "clip": "video", "clips": "video",
    "song": "audio", "songs": "audio", "music": "audio", "audio": "audio",
    "document": "document", "documents": "document", "docs": "document", "doc": "document",
    "code": "code", "script": "code", "scripts": "code",
}
EXT_WORDS = {
    "pdf": ["pdf"], "pdfs": ["pdf"], "spreadsheet": ["xlsx", "xls", "csv"], "spreadsheets": ["xlsx", "xls", "csv"],
    "excel": ["xlsx", "xls"], "presentation": ["pptx", "ppt"], "presentations": ["pptx", "ppt"],
    "slides": ["pptx", "ppt"], "docx": ["docx"], "csv": ["csv"], "zip": ["zip"], "word": ["docx", "doc"],
}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
UNITS = {"kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}
STOP = set(["the", "a", "an", "of", "from", "in", "on", "at", "to", "for", "and", "my", "me", "i", "with", "that", "this", "is", "was", "were", "it", "its", "by", "as", "are", "be", "last", "past", "file", "files", "find", "show", "get", "all", "any", "some", "those", "these", "about", "during", "over", "under", "older", "newer"])


def _sod(d):  # start of day
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def parse(q: str, now: datetime | None = None) -> tuple[str, dict]:
    now = now or datetime.now()
    t, f = " " + q.lower() + " ", {}

    def cut(m):
        nonlocal t
        t = t[: m.start()] + " " + t[m.end():]

    # --- size
    m = re.search(r"\b(?:larger|bigger|greater|over|above|more)\s+than\s+([\d.]+)\s*(kb|mb|gb|tb)\b", t)
    if m:
        f["min_size"] = int(float(m[1]) * UNITS[m[2]]); cut(m)
    m = re.search(r"\b(?:smaller|less|under|below)\s+than\s+([\d.]+)\s*(kb|mb|gb|tb)\b", t)
    if m:
        f["max_size"] = int(float(m[1]) * UNITS[m[2]]); cut(m)
    m = re.search(r"\b(?:huge|large|big)\s+files?\b", t)
    if m:
        f.setdefault("min_size", 100 * 1024**2); cut(m)

    # --- dates (mtime)
    today = _sod(now)
    after = before = None
    if (m := re.search(r"\byesterday\b", t)):
        after, before = today - timedelta(days=1), today; cut(m)
    elif (m := re.search(r"\btoday\b", t)):
        after, before = today, today + timedelta(days=1); cut(m)
    elif (m := re.search(r"\blast\s+week\b", t)):
        mon = today - timedelta(days=today.weekday())
        after, before = mon - timedelta(days=7), mon; cut(m)
    elif (m := re.search(r"\bthis\s+week\b", t)):
        after = today - timedelta(days=today.weekday()); cut(m)
    elif (m := re.search(r"\blast\s+month\b", t)):
        first = today.replace(day=1)
        after, before = (first - timedelta(days=1)).replace(day=1), first; cut(m)
    elif (m := re.search(r"\bthis\s+month\b", t)):
        after = today.replace(day=1); cut(m)
    elif (m := re.search(r"\blast\s+year\b", t)):
        after, before = datetime(now.year - 1, 1, 1), datetime(now.year, 1, 1); cut(m)
    elif (m := re.search(r"\bthis\s+year\b", t)):
        after = datetime(now.year, 1, 1); cut(m)
    elif (m := re.search(r"\b(?:last|previous)\s+semester\b", t)):
        after, before = today - timedelta(days=210), today - timedelta(days=21); cut(m)  # ~ the previous 6 months
    elif (m := re.search(r"\b(?:last|past)\s+(\d+)\s+(day|week|month|year)s?\b", t)):
        n = int(m[1]) * {"day": 1, "week": 7, "month": 30, "year": 365}[m[2]]
        after = today - timedelta(days=n); cut(m)
    elif (m := re.search(r"\b(?:in\s+)?(" + "|".join(MONTHS) + r")\b(?:\s+(\d{4}))?", t)) and (m[2] or "in " in m[0] or len(m[1]) > 3):
        mo, yr = MONTHS[m[1]], int(m[2]) if m[2] else None
        if yr is None:
            yr = now.year if mo <= now.month else now.year - 1
        after = datetime(yr, mo, 1)
        before = datetime(yr + (mo == 12), mo % 12 + 1, 1); cut(m)
    elif (m := re.search(r"\b(?:in\s+|from\s+|of\s+)?((?:19|20)\d\d)\b", t)):
        after, before = datetime(int(m[1]), 1, 1), datetime(int(m[1]) + 1, 1, 1); cut(m)
    if after:
        f["after"] = after.timestamp()
    if before:
        f["before"] = before.timestamp()

    # --- file type words
    words = re.findall(r"[\w]+", t)
    kinds, exts, keep = [], [], []
    for w in words:
        if w in KIND_WORDS:
            kinds.append(KIND_WORDS[w])
        elif w in EXT_WORDS:
            exts += EXT_WORDS[w]
        else:
            keep.append(w)
    if kinds:
        f["kinds"] = sorted(set(kinds))
    if exts:
        f["exts"] = sorted(set(exts))
    text = " ".join(w for w in keep if w not in STOP)
    return text, f
