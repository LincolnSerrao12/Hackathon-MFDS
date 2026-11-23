"""FastAPI app: search, sources, indexing status, stats. Serves the static UI."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db, sources
from . import search as searchmod
from .indexer import indexer

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app):
    db.connect()
    indexer.resume_all()
    yield
    indexer.shutdown()


app = FastAPI(title="ME3 File System Intelligence", lifespan=lifespan)


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
    natural: bool = True, limit: int = Query(50, le=200), offset: int = 0,
):
    flt = {
        "kinds": [k for k in kind.split(",") if k] or None, "exts": [e.lower().lstrip(".") for e in ext.split(",") if e] or None,
        "min_size": min_size, "max_size": max_size, "after": after, "before": before, "source_id": source_id,
    }
    flt = {k: v for k, v in flt.items() if v is not None}
    return searchmod.search(db.get(), q, flt, natural, limit, offset)


@app.get("/api/stats")
def stats():
    c = db.get()
    by_kind = [dict(r) for r in c.execute("SELECT kind, count(*) AS n, coalesce(sum(size),0) AS bytes FROM files GROUP BY kind ORDER BY bytes DESC")]
    tot = c.execute("SELECT count(*) AS n, coalesce(sum(size),0) AS bytes FROM files").fetchone()
    pend = c.execute("SELECT count(*) FROM files WHERE extracted=0").fetchone()[0]
    return {"files": tot["n"], "bytes": tot["bytes"], "pending_extraction": pend, "by_kind": by_kind}


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
    sid = sources.add_source(db.get(), s.kind, s.root, s.name, s.config)
    indexer.start_source(sid)
    return {"id": sid}


@app.post("/api/sources/{sid}/reindex")
def reindex(sid: int):
    if not sources.load(db.get(), sid):
        raise HTTPException(404)
    indexer.start_source(sid)
    return {"ok": True}


@app.get("/api/index/status")
def index_status():
    return indexer.snapshot()
