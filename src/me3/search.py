"""Hybrid search: FTS5 keywords (bm25) + MiniLM text meaning + CLIP image meaning, fused with reciprocal rank fusion (RRF),
then filtered by type/size/date. Falls back to keyword-only when embeddings are unavailable."""
import re
from datetime import datetime

from . import embed, nlq

RRF_K = 60
MIN_TEXT_COS = 0.30  # MiniLM cosine below this is noise
MIN_IMG_COS_FORCED = 0.18  # user asked for images/photos: show the best matches
MIN_IMG_COS_OPEN = 0.26  # image results mixed into a generic query must be a clear match


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


def _has_vectors(conn) -> bool:
    return embed.available() and conn.execute("SELECT count(*) FROM sqlite_master WHERE name IN ('vec_text','vec_img')").fetchone()[0] > 0


def _knn(conn, table: str, qvec, k: int, min_cos: float) -> list[int]:
    rows = conn.execute(f"SELECT file_id, distance FROM {table} WHERE embedding MATCH ? AND k=?", (embed._blob(qvec), k)).fetchall()
    return [r["file_id"] for r in rows if 1.0 - r["distance"] >= min_cos]


def _hybrid(conn, text: str, flt: dict, limit: int, offset: int, phrase: str = "") -> dict:
    phrase = nlq.expand(phrase or text)  # widened only for the on-device meaning query
    w, p = _filters(flt)
    where = (" AND " + " AND ".join(w)) if w else ""
    rank_lists: dict[str, list[int]] = {}
    snips: dict[int, str] = {}
    match = _fts_query(text)
    if match:
        rows = conn.execute(
            "SELECT f.id, snippet(fts,2,'<mark>','</mark>','…',14) AS snip FROM fts JOIN files f ON f.id=fts.rowid "
            f"WHERE fts MATCH ?{where} ORDER BY bm25(fts,6.0,2.0,1.0) LIMIT 300", [match, *p]).fetchall()
        rank_lists["keyword"] = [r["id"] for r in rows]
        snips = {r["id"]: r["snip"] for r in rows}
    embed.load_vec(conn)
    kinds = flt.get("kinds") or []
    wants_images = not kinds or "image" in kinds
    cand: dict[str, list[int]] = {"meaning": _knn(conn, "vec_text", embed.embed_query_text(phrase), 400, MIN_TEXT_COS)}
    if wants_images and not flt.get("exts"):
        cand["image"] = _knn(conn, "vec_img", embed.embed_query_image_space(phrase), 300,
                             MIN_IMG_COS_FORCED if "image" in kinds else MIN_IMG_COS_OPEN)
    allc = sorted({i for v in cand.values() for i in v})
    ok: set[int] = set()
    for i in range(0, len(allc), 500):  # apply filters to vector candidates
        chunk = allc[i : i + 500]
        ok |= {r["id"] for r in conn.execute(f"SELECT f.id FROM files f WHERE f.id IN ({','.join('?' * len(chunk))}){where}", [*chunk, *p])}
    for name, ids in cand.items():
        rank_lists[name] = [i for i in ids if i in ok]
    score: dict[int, float] = {}
    why: dict[int, list[str]] = {}
    for name, ids in rank_lists.items():
        for r, i in enumerate(ids):
            score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + r + 1)
            why.setdefault(i, []).append(name)
    fused = sorted(score, key=lambda i: -score[i])
    page = fused[offset : offset + limit]
    items = []
    if page:
        q = ",".join("?" * len(page))
        by_id = {r["id"]: r for r in conn.execute(
            f"SELECT f.*, s.name AS source, substr(fts.body,1,160) AS head FROM files f JOIN fts ON fts.rowid=f.id LEFT JOIN sources s ON s.id=f.source_id WHERE f.id IN ({q})", page)}
        for i in page:
            r = by_id.get(i)
            if r is None:
                continue
            d = _item(dict(r) | {"snip": snips.get(i) or (r["head"] or "")})
            d["why"] = why[i]
            items.append(d)
    return {"total": len(fused), "results": items}


def search(conn, q: str = "", filters: dict | None = None, natural: bool = True, limit: int = 50, offset: int = 0, semantic: bool = True) -> dict:
    flt = dict(filters or {})
    text = phrase = q
    parsed = {}
    if natural and q.strip():
        text, parsed, phrase = nlq.parse_full(q)
        for k, v in parsed.items():
            flt.setdefault(k, v)  # explicit filters win over parsed ones
    mode = "keyword"
    if semantic and text.strip() and _has_vectors(conn):
        try:
            h = _hybrid(conn, text, flt, limit, offset, phrase)
            return {"query": q, "text": text, "filters": dict(flt), "mode": "hybrid", **h}
        except Exception:  # embeddings broken/unavailable: keyword search still works
            pass
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
    return {"query": q, "text": text, "filters": {k: v for k, v in flt.items()}, "mode": mode, "total": cnt,
            "results": [_item(r) for r in rows]}
