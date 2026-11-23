"""Text extraction for the full-text index (txt/code/pdf/docx). Runs after the crawl, in the background."""
import os

from . import sources as srcmod

MAX_CHARS = int(os.environ.get("ME3_MAX_CHARS", 20_000))  # per file stored in the index
MAX_BYTES = 80 * 1024 * 1024  # skip reading files larger than this


def read_text(path: str, ext: str) -> str:
    if ext == "pdf":
        from pypdf import PdfReader

        parts, total = [], 0
        for page in PdfReader(path).pages[:40]:
            t = page.extract_text() or ""
            parts.append(t)
            total += len(t)
            if total >= MAX_CHARS:
                break
        return "\n".join(parts)[:MAX_CHARS]
    if ext == "docx":
        import docx

        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" ".join(c.text for c in row.cells))
        return "\n".join(parts)[:MAX_CHARS]
    with open(path, "rb") as f:
        raw = f.read(MAX_CHARS * 4)
    if b"\0" in raw[:2048]:
        return ""
    return raw.decode("utf-8", "ignore")[:MAX_CHARS]


def run_pending(conn, progress=None, should_stop=lambda: False, batch: int = 200, limit: int | None = None) -> int:
    """Extract text for files with extracted=0. Returns number processed."""
    cache, done = {}, 0
    while not should_stop():
        rows = conn.execute(
            "SELECT id,source_id,path,ext,size FROM files WHERE extracted=0 LIMIT ?", (batch,)
        ).fetchall()
        if not rows:
            break
        for r in rows:
            if should_stop():
                break
            body, status = "", 2
            if r["size"] <= MAX_BYTES:
                try:
                    src = cache.get(r["source_id"]) or cache.setdefault(r["source_id"], srcmod.load(conn, r["source_id"]))
                    with src.fetch(r["path"]) as local:
                        body = read_text(local, r["ext"])
                    status = 1 if body.strip() else 2
                except Exception:
                    status = 3
            if body:
                conn.execute("UPDATE fts SET body=? WHERE rowid=?", (body, r["id"]))
            conn.execute("UPDATE files SET extracted=? WHERE id=?", (status, r["id"]))
            done += 1
        conn.commit()
        if progress:
            progress(done)
        if limit and done >= limit:
            break
    return done
