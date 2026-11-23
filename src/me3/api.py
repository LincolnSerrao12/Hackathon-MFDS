"""FastAPI app: search, sources, indexing status, stats. Serves the static UI."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from . import auth, cleanup, db, embed, llm, privacy, sources
from . import search as searchmod
from .indexer import indexer

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app):
    db.connect()
    indexer.resume_all()
    if embed.available():
        import threading
        threading.Thread(target=lambda: (embed._model(embed.TEXT_MODEL), embed._model(embed.IMG_MODEL)), daemon=True).start()  # warm models
    yield
    indexer.shutdown()


app = FastAPI(title="ME3 File System Intelligence", lifespan=lifespan)
app.middleware("http")(auth.require_login)
app.include_router(auth.router)


class SourceIn(BaseModel):
    kind: str = "local"
    root: str
    name: str = ""
    config: dict = {}


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/search")
def api_search(
    q: str = "", kind: str = "", ext: str = "", min_size: int | None = None, max_size: int | None = None,
    after: float | None = None, before: float | None = None, source_id: int | None = None,
    natural: bool = True, semantic: bool = True, limit: int = Query(50, le=200), offset: int = 0,
):
    flt = {
        "kinds": [k for k in kind.split(",") if k] or None, "exts": [e.lower().lstrip(".") for e in ext.split(",") if e] or None,
        "min_size": min_size, "max_size": max_size, "after": after, "before": before, "source_id": source_id,
    }
    flt = {k: v for k, v in flt.items() if v is not None}
    return searchmod.search(db.get(), q, flt, natural, limit, offset, semantic)


@app.get("/api/stats")
def stats():
    c = db.get()
    by_kind = [dict(r) for r in c.execute("SELECT kind, count(*) AS n, coalesce(sum(size),0) AS bytes FROM files GROUP BY kind ORDER BY bytes DESC")]
    tot = c.execute("SELECT count(*) AS n, coalesce(sum(size),0) AS bytes FROM files").fetchone()
    pend = c.execute("SELECT count(*) FROM files WHERE extracted=0").fetchone()[0]
    return {"files": tot["n"], "bytes": tot["bytes"], "pending_extraction": pend, "by_kind": by_kind,
            "semantic": embed.available(), "embedding": embed.pending_counts(c)}


@app.get("/api/insights")
def insights(months: int = Query(24, ge=6, le=120), top: int = Query(10, ge=3, le=50)):
    """Aggregates for the Overview charts: activity per month, biggest folders, size buckets, sources, index progress."""
    import os
    import time as _t
    from collections import defaultdict
    c = db.get()
    now = _t.localtime()
    keys = []
    y, m = now.tm_year, now.tm_mon
    for _ in range(months):  # oldest -> newest, every month present even when empty
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    keys.reverse()
    per = {r[0]: (r[1], r[2]) for r in c.execute(
        "SELECT strftime('%Y-%m', mtime, 'unixepoch', 'localtime') AS ym, count(*), coalesce(sum(size),0) FROM files "
        "WHERE ym >= ? GROUP BY ym", (keys[0],))}
    timeline = [{"month": k, "n": per.get(k, (0, 0))[0], "bytes": per.get(k, (0, 0))[1]} for k in keys]

    roots = {r["id"]: (r["root"] or "/", r["name"], r["kind"]) for r in c.execute("SELECT id, root, name, kind FROM sources")}
    folders: dict = defaultdict(lambda: [0, 0])
    for r in c.execute("SELECT source_id, path, size FROM files"):
        root, name, kind = roots.get(r["source_id"], ("/", "?", "local"))
        rel = os.path.relpath(r["path"], root) if kind == "local" else r["path"].split("#")[0].lstrip("/")
        parts = [p for p in rel.replace("\\", "/").split("/")[:-1] if p]
        key = (name, "/".join(parts[:2]) or "(top level)")
        folders[key][0] += 1
        folders[key][1] += r["size"]
    big = sorted(folders.items(), key=lambda kv: -kv[1][1])[:top]

    edges = [(0, "< 100 KB"), (100 << 10, "100 KB – 1 MB"), (1 << 20, "1 – 10 MB"), (10 << 20, "10 – 100 MB"), (100 << 20, "100 MB – 1 GB"), (1 << 30, "> 1 GB")]
    sizes = []
    for i, (lo, label) in enumerate(edges):
        hi = edges[i + 1][0] if i + 1 < len(edges) else 1 << 62
        n, b = c.execute("SELECT count(*), coalesce(sum(size),0) FROM files WHERE size >= ? AND size < ?", (lo, hi)).fetchone()
        sizes.append({"label": label, "n": n, "bytes": b})

    srcs = [dict(r) for r in c.execute("SELECT s.name, s.kind, count(f.id) AS n, coalesce(sum(f.size),0) AS bytes "
                                        "FROM sources s LEFT JOIN files f ON f.source_id=s.id GROUP BY s.id ORDER BY bytes DESC")]
    p = c.execute("SELECT sum(extracted=1) AS ex, sum(extracted IN (0,1,3)) AS exable, sum(embedded=1) AS em, "
                  "sum(embedded IN (0,1)) AS emable FROM files").fetchone()
    return {"timeline": timeline, "folders": [{"source": k[0], "folder": k[1], "n": v[0], "bytes": v[1]} for k, v in big],
            "sizes": sizes, "sources": srcs,
            "progress": {"text_done": p["ex"] or 0, "text_total": p["exable"] or 0, "meaning_done": p["em"] or 0, "meaning_total": p["emable"] or 0}}


@app.get("/api/sources")
def list_sources():
    c = db.get()
    out = []
    for r in c.execute("SELECT s.*, (SELECT count(*) FROM files WHERE source_id=s.id) AS files FROM sources s ORDER BY id"):
        d = dict(r)
        d.pop("config", None)
        d["index"] = indexer.snapshot().get(r["id"])
        out.append(d)
    return out


@app.post("/api/sources")
def add_source(s: SourceIn):
    if s.kind == "local":
        import os
        if not os.path.isdir(s.root):
            raise HTTPException(400, f"not a directory: {s.root}")
        new = os.path.realpath(s.root)
        for r in db.get().execute("SELECT name, root FROM sources WHERE kind='local'"):
            old = os.path.realpath(r["root"])
            if new == old or new.startswith(old.rstrip("/") + "/"):
                raise HTTPException(400, f"already indexed: {new} is inside '{r['name']}' ({old}), so its files are searchable already")
            if old.startswith(new.rstrip("/") + "/"):
                raise HTTPException(400, f"{new} contains the existing source '{r['name']}' ({old}); remove that one first to avoid duplicate results")
    elif s.kind == "gdrive":
        from .connectors.gdrive import GDriveSource
        probe = GDriveSource(0, s.root or "/", s.name, s.config)
        root = s.root or "/"
        for r in db.get().execute("SELECT name, root FROM sources WHERE kind='gdrive'"):
            if r["root"] == root:
                raise HTTPException(400, f"'{r['name']}' already covers that")
            if "/" in (root, r["root"]):
                raise HTTPException(400, f"'{r['name']}' ({'whole Drive' if r['root'] == '/' else r['root']}) overlaps: remove it first to avoid duplicate results")
        try:
            probe.test()
        except Exception as e:
            raise HTTPException(400, f"cannot connect: {e}") from e
    else:
        raise HTTPException(400, f"unknown source kind {s.kind}")
    sid = sources.add_source(db.get(), s.kind, s.root or "/", s.name, s.config)
    indexer.start_source(sid)
    return {"id": sid}


@app.get("/api/gdrive/status")
def gdrive_status():
    from .connectors import gdrive
    try:
        client = gdrive.find_client_secret().name
    except RuntimeError:
        client = None
    added = db.get().execute("SELECT 1 FROM sources WHERE kind='gdrive'").fetchone() is not None
    return {"client_file": client, "authorised": gdrive.TOKEN.exists(), "added": added, "authorising": _gd_auth.get("running", False),
            "error": _gd_auth.get("error")}


_gd_auth: dict = {}


@app.post("/api/gdrive/authorize")
def gdrive_authorize():
    """Runs the one-time Google consent in the server's own browser (this app is local). Same client_secret file as sign-in."""
    import threading

    from .connectors import gdrive
    if _gd_auth.get("running"):
        return {"ok": True}
    gdrive.find_client_secret()

    def run():
        _gd_auth.update(running=True, error=None)
        try:
            gdrive.authorize(open_browser=True)
        except Exception as e:  # noqa: BLE001
            _gd_auth["error"] = str(e)[:300]
        _gd_auth["running"] = False
    threading.Thread(target=run, daemon=True, name="gdrive-auth").start()
    return {"ok": True}


@app.delete("/api/sources/{sid}")
def remove_source(sid: int):
    if not sources.load(db.get(), sid):
        raise HTTPException(404)
    if not indexer.remove_source(sid):
        raise HTTPException(409, "this source is being indexed right now; try again when it is idle")
    return {"ok": True}


@app.post("/api/sources/{sid}/reindex")
def reindex(sid: int):
    if not sources.load(db.get(), sid):
        raise HTTPException(404)
    indexer.start_source(sid)
    return {"ok": True}


@app.get("/api/index/status")
def index_status():
    return indexer.snapshot()


# ---------------------------------------------------------------- cleanup
@app.get("/api/cleanup/summary")
def cleanup_summary():
    return cleanup.summary(db.get())


@app.get("/api/cleanup/duplicates")
def cleanup_duplicates(min_size: int = 1024, limit: int = 50):
    return cleanup.find_duplicates(db.get(), min_size=min_size, limit_groups=limit)


@app.get("/api/cleanup/large")
def cleanup_large(limit: int = 50, min_mb: int = 50):
    return cleanup.large_files(db.get(), limit, min_mb * 1024 * 1024)


@app.get("/api/cleanup/stale")
def cleanup_stale(days: int = 365, limit: int = 50):
    return cleanup.stale_media(db.get(), days, limit)


# ---------------------------------------------------------------- viewing files (so users can check before trashing)
PREVIEW_TEXT = 6000
RAW_MAX_REMOTE = 60 * 1024 * 1024
UNSAFE_INLINE = {"html", "htm", "svg", "xml", "xhtml", "js", "mjs"}  # never render these as active content in our origin


def _file_row(fid: int):
    r = db.get().execute("SELECT f.*, s.kind AS skind, s.name AS source FROM files f JOIN sources s ON s.id=f.source_id WHERE f.id=?", (fid,)).fetchone()
    if not r:
        raise HTTPException(404, "file is no longer in the index")
    return r


@app.get("/api/files/{fid}")
def file_info(fid: int):
    """Metadata + a text preview (from the index, or read directly for small local text files)."""
    import os
    from datetime import datetime

    from .util import TEXT_EXTS
    r = _file_row(fid)
    body = db.get().execute("SELECT substr(body,1,?) FROM fts WHERE rowid=?", (PREVIEW_TEXT, fid)).fetchone()
    text = (body[0] if body else "") or ""
    if not text and r["skind"] == "local" and r["ext"] in TEXT_EXTS and r["size"] <= 2 * 1024 * 1024:
        try:
            with open(r["path"], encoding="utf-8", errors="replace") as fh:
                text = fh.read(PREVIEW_TEXT)
        except OSError:
            pass
    exists = os.path.exists(r["path"]) if r["skind"] == "local" else True
    return {"id": r["id"], "name": r["name"], "path": r["path"], "ext": r["ext"], "kind": r["kind"], "size": r["size"],
            "modified": datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M"), "source": r["source"], "local": r["skind"] == "local",
            "exists": exists, "hash": r["hash"], "text": text, "inline": r["ext"] not in UNSAFE_INLINE}


@app.get("/api/files/{fid}/raw")
def file_raw(fid: int):
    """The file itself, for the in-app viewer (images, PDF, audio, video). Active formats are sent as plain text."""
    import mimetypes
    import os

    r = _file_row(fid)
    mime = "text/plain; charset=utf-8" if r["ext"] in UNSAFE_INLINE else (mimetypes.guess_type(r["name"])[0] or "application/octet-stream")
    headers = {"X-Content-Type-Options": "nosniff", "Content-Disposition": "inline", "Cache-Control": "private, max-age=60"}
    if not mime.startswith(("image/", "video/", "audio/", "application/pdf")) or mime == "image/svg+xml":
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'"  # browsers' PDF/media viewers break under sandbox; others never run
    if r["skind"] == "local":
        if not os.path.isfile(r["path"]):
            raise HTTPException(404, "file not found on disk (moved or deleted?)")
        return FileResponse(r["path"], media_type=mime, headers=headers)
    if r["size"] > RAW_MAX_REMOTE:
        raise HTTPException(413, "too large to preview from Drive; open it in Google Drive instead")
    src = sources.load(db.get(), r["source_id"])
    try:
        with src.fetch(r["path"]) as local, open(local, "rb") as fh:
            data = fh.read()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"could not download from {r['source']}: {e}") from e
    return Response(data, media_type=mime, headers=headers)


class OpenIn(BaseModel):
    reveal: bool = False  # True = show the file in its folder instead of opening it


@app.post("/api/files/{fid}/open")
def file_open(fid: int, o: OpenIn):
    """Open a local file with the computer's default app, or show it in the file manager (this app runs on the user's own machine)."""
    import os
    import subprocess
    import sys

    r = _file_row(fid)
    if r["skind"] != "local":
        raise HTTPException(400, "only files on this computer can be opened here")
    path = r["path"]
    if not os.path.exists(path):
        raise HTTPException(404, "file not found on disk (moved or deleted?)")
    try:
        if sys.platform.startswith("win"):
            if o.reveal:
                subprocess.Popen(["explorer", "/select,", path])
            else:
                os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path] if o.reveal else ["open", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path) if o.reveal else path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"could not open: {e}") from e
    return {"ok": True}


@app.get("/api/folder")
def folder_files(path: str, limit: int = Query(200, le=1000)):
    """Files directly inside one folder (used by Organise -> View files)."""
    from datetime import datetime
    pre = path.rstrip("/\\")
    esc_ = pre.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = db.get().execute(
        "SELECT id,name,path,kind,ext,size,mtime FROM files WHERE path LIKE ? ESCAPE '\\' AND path NOT LIKE ? ESCAPE '\\' ORDER BY kind, name LIMIT ?",
        (esc_ + "/%", esc_ + "/%/%", limit)).fetchall()
    total = db.get().execute("SELECT count(*) FROM files WHERE path LIKE ? ESCAPE '\\' AND path NOT LIKE ? ESCAPE '\\'", (esc_ + "/%", esc_ + "/%/%")).fetchone()[0]
    return {"folder": pre, "total": total, "files": [dict(r) | {"modified": datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M")} for r in rows]}


class TrashIn(BaseModel):
    ids: list[int]


@app.post("/api/cleanup/trash")
def cleanup_trash(t: TrashIn):
    """Reversible: files are moved to data/trash/<timestamp>/ with a MANIFEST of original paths."""
    return cleanup.trash_files(db.get(), t.ids)


# ---------------------------------------------------------------- privacy + AI suggestions
class RedactIn(BaseModel):
    text: str


@app.post("/api/privacy/redact")
def privacy_redact(r: RedactIn):
    out = privacy.redact(r.text)
    return {"redacted": out.text, "counts": out.counts}


class SuggestIn(BaseModel):
    source_id: int | None = None
    send: bool = False  # False = preview only; nothing leaves the machine
    sample: int = 60


@app.post("/api/suggest")
def suggest(s: SuggestIn):
    """Organisation suggestions. Always returns rule-based ideas (on-device) and the exact redacted payload.
    The payload is sent to the cloud LLM only when send=true AND an API key is configured."""
    c = db.get()
    ideas = cleanup.organisation_ideas(c, s.source_id)
    rows = []
    for i in ideas[:4]:  # sample from the messiest folders, then pad with random files
        rows += c.execute("SELECT * FROM files WHERE path LIKE ? ESCAPE '\\' ORDER BY random() LIMIT 12",
                          (i["folder"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "/%",)).fetchall()
    rows += c.execute("SELECT * FROM files ORDER BY random() LIMIT ?", (max(0, s.sample - len(rows)),)).fetchall()
    from datetime import datetime
    items = [{"path": r["path"], "name": r["name"], "kind": r["kind"], "ext": r["ext"], "size": r["size"],
              "modified": datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M")} for r in rows]
    payload = privacy.prepare_payload(items)
    out = {"ideas": ideas, "payload": payload, "llm_available": llm.available(), "local": llm.is_local(), "sent": False, "ai": None}
    if s.send:
        if not llm.available():
            raise HTTPException(400, "No AI model available: start Ollama with the gemma4:e4b model (or set ME3_LLM_PROVIDER + a key in .env). Showing on-device suggestions only.")
        try:
            out["ai"], out["sent"] = llm.organise(payload), True
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            if isinstance(e, llm.LLMError):
                code = {400: 400, 401: 401, 403: 401, 404: 400, 429: 429}.get(e.status, 502)
                hint = {401: "Gemini rejected the key: create one at aistudio.google.com/apikey.",
                        429: "Gemini free-tier rate limit hit: wait a minute and retry."}.get(code, f"Gemini request failed: {e}")
                raise HTTPException(code, hint) from e
            if name == "AuthenticationError":
                raise HTTPException(401, "Anthropic rejected the key. It must be a standard API key (sk-ant-api...) from console.anthropic.com, not an sk-ant-usr key.") from e
            if "credit balance" in str(e):
                raise HTTPException(402, "Anthropic API key is valid but the account has no credits: add credits at console.anthropic.com -> Plans & Billing.") from e
            if name in ("NotFoundError", "BadRequestError"):
                raise HTTPException(400, f"Anthropic request failed ({name}): {e}. Check ME3_LLM_MODEL (default {llm.MODEL}).") from e
            raise HTTPException(502, f"Cloud AI call failed ({name}): {e}") from e
    return out


@app.get("/api/llm/status")
def llm_status():
    return {"cloud_available": llm.available() and not llm.is_local(), "ai_available": llm.available(), "local": llm.is_local(), "provider": llm.provider(), "model": llm.model_name()}


@app.get("/api/thumb/{fid}")
def thumb(fid: int, size: int = Query(256, ge=64, le=1280)):
    """JPEG thumbnail (default 256px; the UI preview asks for a larger one) for an image file (local or remote); generated on the fly, never leaves the machine."""
    import io


    c = db.get()
    r = c.execute("SELECT source_id,path,kind,ext FROM files WHERE id=?", (fid,)).fetchone()
    if not r or r["kind"] != "image" or r["ext"] not in embed.IMG_EXTS:
        raise HTTPException(404)
    src = sources.load(c, r["source_id"])
    try:
        with src.fetch(r["path"]) as local:
            im = embed._load_image(local)
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
    except Exception as e:
        raise HTTPException(404, str(e)) from e
    return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})
