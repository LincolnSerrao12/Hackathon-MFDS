"""Cleanup insights: duplicates, large files, stale media, and rule-based organisation ideas (all on-device)."""
import hashlib
import os
import shutil
import time
from collections import defaultdict

from . import crawler, db

TRASH = db.ROOT / "data" / "trash"
PARTIAL = 64 * 1024


def _hash_file(path: str, partial: bool) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(PARTIAL) if partial else b"")
        if not partial:
            f.seek(0)
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


MAX_DUP_BYTES = 512 * 1024 * 1024  # hashing multi-GB files (games, VM images) would take minutes; large_files() lists those


def find_duplicates(conn, min_size: int = 1024, limit_groups: int = 100, source_id: int | None = None) -> dict:
    """size -> partial hash -> full hash. Only local sources are hashed (remote needs a download)."""
    where = "AND source_id=?" if source_id else ""
    args = [min_size] + ([source_id] if source_id else [])
    cand = conn.execute(
        f"""SELECT f.id,f.path,f.size,f.mtime,f.hash FROM files f JOIN sources s ON s.id=f.source_id
            WHERE s.kind='local' AND f.size>=? AND f.size<={MAX_DUP_BYTES} {where.replace('source_id', 'f.source_id')}
              AND f.size IN (SELECT size FROM files WHERE size>=? AND size<={MAX_DUP_BYTES} GROUP BY size HAVING count(*)>1)""",
        args + [min_size],
    ).fetchall()
    by_size = defaultdict(list)
    for r in cand:
        by_size[r["size"]].append(r)
    groups = []
    for size, rows in by_size.items():
        buckets = defaultdict(list)
        for r in rows:  # partial hash first (cheap), then full only inside matching buckets
            try:
                buckets[_hash_file(r["path"], True)].append(r)
            except OSError:
                pass
        for rs in buckets.values():
            if len(rs) < 2:
                continue
            full = defaultdict(list)
            for r in rs:
                try:
                    hv = r["hash"] or _hash_file(r["path"], False)
                    if not r["hash"]:
                        conn.execute("UPDATE files SET hash=? WHERE id=?", (hv, r["id"]))
                    full[hv].append(r)
                except OSError:
                    pass
            conn.commit()  # release the write lock between buckets so the indexer is never starved
            for hv, g in full.items():
                if len(g) > 1:
                    g.sort(key=lambda r: r["mtime"])
                    groups.append({"hash": hv, "size": size, "wasted": size * (len(g) - 1),
                                   "files": [{"id": r["id"], "path": r["path"], "mtime": r["mtime"]} for r in g]})
    conn.commit()
    groups.sort(key=lambda g: -g["wasted"])
    return {"groups": groups[:limit_groups], "total_groups": len(groups), "wasted_bytes": sum(g["wasted"] for g in groups)}


def large_files(conn, limit: int = 50, min_size: int = 50 * 1024 * 1024) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id,path,name,kind,size,mtime FROM files WHERE size>=? ORDER BY size DESC LIMIT ?", (min_size, limit))]


def stale_media(conn, days: int = 365, limit: int = 50, min_size: int = 1024 * 1024) -> list[dict]:
    cutoff = time.time() - days * 86400
    return [dict(r) for r in conn.execute(
        "SELECT id,path,name,kind,size,mtime FROM files WHERE kind IN ('video','archive','image','audio') AND mtime<? AND size>=? "
        "ORDER BY size DESC LIMIT ?", (cutoff, min_size, limit))]


def organisation_ideas(conn, source_id: int | None = None, max_ideas: int = 12) -> list[dict]:
    """Rule-based suggestions from metadata only. Works offline; the LLM (llm.py) refines wording on redacted data."""
    q = "SELECT path,kind,mtime,size FROM files" + (" WHERE source_id=?" if source_id else "")
    dirs = defaultdict(list)
    for r in conn.execute(q, [source_id] if source_id else []):
        dirs[os.path.dirname(r["path"])].append(r)
    ideas = []
    for d, rows in dirs.items():
        n = len(rows)
        if n < 20:
            continue
        kinds = defaultdict(int)
        for r in rows:
            kinds[r["kind"]] += 1
        major = [k for k, c in kinds.items() if c >= 8]
        years = {time.gmtime(r["mtime"]).tm_year for r in rows}
        if len(major) >= 2:
            ideas.append({"folder": d, "files": n, "score": n, "action": "split_by_type",
                          "title": f"Split by type: {', '.join(sorted(major))}",
                          "detail": f"{n} files of mixed types share one folder; move each type to its own sub-folder."})
        elif n >= 50 and len(years) >= 3:
            ideas.append({"folder": d, "files": n, "score": n * 0.8, "action": "group_by_year",
                          "title": f"Group by year ({min(years)}-{max(years)})",
                          "detail": f"{n} files span {len(years)} years; year sub-folders make them browsable."})
        unnamed = sum(1 for r in rows if os.path.basename(r["path"]).lower().startswith(("img_", "dsc", "screenshot", "untitled", "new ")))
        if unnamed >= 20:
            ideas.append({"folder": d, "files": unnamed, "score": unnamed * 0.9, "action": "rename_unnamed",
                          "title": "Give camera/untitled files meaningful names",
                          "detail": f"{unnamed} files have generic names (IMG_/DSC/Screenshot...). Semantic search can find them, but albums by event help."})
    ideas.sort(key=lambda i: -i["score"])
    return ideas[:max_ideas]


def summary(conn) -> dict:
    dup = find_duplicates(conn, limit_groups=0)
    big = large_files(conn, limit=1000)
    stale = stale_media(conn, limit=100000)
    return {"duplicate_groups": dup["total_groups"], "duplicate_wasted_bytes": dup["wasted_bytes"],
            "large_files": len(big), "large_bytes": sum(f["size"] for f in big),
            "stale_media_files": len(stale), "stale_media_bytes": sum(f["size"] for f in stale)}


def trash_files(conn, ids: list[int]) -> dict:
    """Reversible delete: move local files into data/trash/<timestamp>/ and drop them from the index."""
    dest = TRASH / time.strftime("%Y%m%d-%H%M%S")
    moved, errors = [], []
    for fid in ids:
        r = conn.execute("SELECT f.id,f.path,f.source_id,s.kind FROM files f JOIN sources s ON s.id=f.source_id WHERE f.id=?", (fid,)).fetchone()
        if not r or r["kind"] != "local":
            errors.append({"id": fid, "error": "not a local file"})
            continue
        try:
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / f"{fid}__{os.path.basename(r['path'])}"
            shutil.move(r["path"], target)
            (dest / "MANIFEST.tsv").open("a").write(f"{target.name}\t{r['path']}\n")
            moved.append(fid)
        except OSError as e:
            errors.append({"id": fid, "error": str(e)})
    crawler.remove_ids(conn, moved)
    conn.commit()
    return {"moved": len(moved), "errors": errors, "trash_dir": str(dest) if moved else None}
