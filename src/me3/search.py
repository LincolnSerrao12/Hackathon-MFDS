"""Search: FTS5 (bm25, name boosted) + filters. Vector re-ranking is added in embed.py/search_semantic later."""
import re
from datetime import datetime

from . import nlq


def _fts_query(text: str) -> str:
    toks = re.findall(r"\w+", text.lower())
    return " OR ".join(f'"{t}"*' for t in toks)


def _filters(flt: dict):
    w, p = [], []
    if flt.get("kinds"):
        w.append(f"f.kind IN ({','.join('?' * len(flt['kinds']))})"); p += flt["kinds"]
    if flt.get("exts"):
        w.append(f"f.ext IN ({','.join('?' * len(flt['exts']))})"); p += flt["exts"]
    if flt.get("source_id"):
        w.append("f.source_id=?"); p.append(flt["source_id"])
    for key, col, op in (("min_size", "size", ">="), ("max_size", "size", "<="), ("after", "mtime", ">="), ("before", "mtime", "<")):
        if flt.get(key) is not None:
            w.append(f"f.{col} {op} ?"); p.append(flt[key])
    return w, p


def _item(r) -> dict:
    return {
        "id": r["id"], "path": r["path"], "name": r["name"], "ext": r["ext"], "kind": r["kind"],
        "size": r["size"], "mtime": r["mtime"], "modified": datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M"),
        "source": r["source"], "snippet": r["snip"] if "snip" in r.keys() else "",
    }


def search(conn, q: str = "", filters: dict | None = None, natural: bool = True, limit: int = 50, offset: int = 0) -> dict:
    flt = dict(filters or {})
    text = q
    parsed = {}
    if natural and q.strip():
        text, parsed = nlq.parse(q)
        for k, v in parsed.items():
            flt.setdefault(k, v)  # explicit filters win over parsed ones
    w, p = _filters(flt)
    match = _fts_query(text)
    where = (" AND " + " AND ".join(w)) if w else ""
    if match:
        sql = (
            "SELECT f.*, s.name AS source, snippet(fts,2,'<mark>','</mark>','…',14) AS snip, bm25(fts,6.0,2.0,1.0) AS score "
            "FROM fts JOIN files f ON f.id=fts.rowid LEFT JOIN sources s ON s.id=f.source_id "
            f"WHERE fts MATCH ?{where} ORDER BY score LIMIT ? OFFSET ?"
        )
        rows = conn.execute(sql, [match, *p, limit, offset]).fetchall()
        cnt = conn.execute(
            f"SELECT count(*) FROM (SELECT 1 FROM fts JOIN files f ON f.id=fts.rowid WHERE fts MATCH ?{where} LIMIT 10001)",
            [match, *p],
        ).fetchone()[0]
    else:
        wh = ("WHERE " + " AND ".join(w)) if w else ""
        rows = conn.execute(
            "SELECT f.*, s.name AS source, '' AS snip FROM files f LEFT JOIN sources s ON s.id=f.source_id "
            f"{wh} ORDER BY f.mtime DESC LIMIT ? OFFSET ?", [*p, limit, offset],
        ).fetchall()
        cnt = conn.execute(f"SELECT count(*) FROM (SELECT 1 FROM files f {wh} LIMIT 10001)", p).fetchone()[0]
    return {"query": q, "text": text, "filters": {k: v for k, v in flt.items()}, "total": cnt,
            "results": [_item(r) for r in rows]}
