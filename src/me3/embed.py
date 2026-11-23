"""Local semantic layer (nothing leaves the machine): MiniLM text embeddings + CLIP image embeddings in sqlite-vec.

- vec_text: 384-d MiniLM (all-MiniLM-L6-v2) of "filename + first ~1500 chars of text"
- vec_img : 512-d CLIP (clip-ViT-B-32) of image pixels; the same model embeds text queries into the same space,
            so "photos from the Goa beach trip" finds beach photos with generic names like IMG_0412.jpg
Embedding runs lazily in the background at low priority (embedded: 0 pending, 1 done, 2 skipped/failed).
"""
import os
import struct
import threading

from . import sources as srcmod

TEXT_MODEL = os.environ.get("ME3_TEXT_MODEL", "all-MiniLM-L6-v2")
IMG_MODEL = os.environ.get("ME3_IMG_MODEL", "clip-ViT-B-32")
IMG_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff"}
MAX_IMG_BYTES = 40 * 1024 * 1024
_models: dict = {}
_mlock = threading.Lock()
_loaded_conns: set[int] = set()


def available() -> bool:
    from importlib.util import find_spec

    return find_spec("sentence_transformers") is not None and find_spec("sqlite_vec") is not None  # cheap: no torch import


def _model(name: str):
    with _mlock:
        if name not in _models:
            import torch
            from sentence_transformers import SentenceTransformer

            torch.set_num_threads(max(1, (os.cpu_count() or 4) // 4))  # leave the machine responsive
            _models[name] = SentenceTransformer(name, device="cpu")
        return _models[name]


def _blob(vec) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def load_vec(conn) -> None:
    """Load sqlite-vec into this connection and make sure the vector tables exist."""
    if id(conn) in _loaded_conns:
        return
    import sqlite_vec

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vec_text USING vec0(file_id integer primary key, embedding float[384] distance_metric=cosine)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vec_img USING vec0(file_id integer primary key, embedding float[512] distance_metric=cosine)")
    _loaded_conns.add(id(conn))


def delete_vectors(conn, ids) -> None:
    if not ids or not available():
        return
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='vec_text'").fetchone():
            return  # nothing embedded yet
        load_vec(conn)
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            q = ",".join("?" * len(chunk))
            conn.execute(f"DELETE FROM vec_text WHERE file_id IN ({q})", chunk)
            conn.execute(f"DELETE FROM vec_img WHERE file_id IN ({q})", chunk)
    except Exception:
        pass


def embed_text(texts: list[str]):
    return _model(TEXT_MODEL).encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)


def embed_query_text(q: str):
    return embed_text([q])[0]


def embed_query_image_space(q: str):
    return _model(IMG_MODEL).encode([q], normalize_embeddings=True, show_progress_bar=False)[0]


def _load_image(path: str):
    from PIL import Image

    im = Image.open(path)
    im.draft("RGB", (448, 448))  # fast JPEG downscale on decode
    im = im.convert("RGB")
    im.thumbnail((448, 448))
    return im


def pending_counts(conn) -> dict:
    r = conn.execute("SELECT sum(embedded=0 AND extracted=1) AS t, sum(embedded=0 AND kind='image') AS i, sum(embedded=1) AS done FROM files").fetchone()
    return {"text": r["t"] or 0, "images": r["i"] or 0, "done": r["done"] or 0}


def run_pending(conn, progress=None, should_stop=lambda: False, limit: int | None = None, batch: int = 64) -> int:
    """Embed text (cheap) then images (slower). Returns files processed."""
    if not available():
        return 0
    load_vec(conn)
    done = 0
    # nothing to embed for files with no text and not an embeddable image -> mark skipped (only once extraction is final)
    conn.execute("UPDATE files SET embedded=2 WHERE embedded=0 AND extracted IN (2,3) AND NOT (kind='image' AND ext IN ('jpg','jpeg','png','webp','bmp','gif','tif','tiff'))")
    conn.commit()
    while not should_stop():  # ---- text
        rows = conn.execute(
            "SELECT f.id,f.name,fts.body FROM files f JOIN fts ON fts.rowid=f.id WHERE f.embedded=0 AND f.extracted=1 LIMIT ?", (batch,)).fetchall()
        if not rows:
            break
        vecs = embed_text([f"{r['name']}. {(r['body'] or '')[:1500]}" for r in rows])
        ids = [r["id"] for r in rows]
        delete_vectors(conn, ids)
        conn.executemany("INSERT INTO vec_text(file_id, embedding) VALUES (?,?)", [(i, _blob(v)) for i, v in zip(ids, vecs)])
        conn.execute(f"UPDATE files SET embedded=1 WHERE id IN ({','.join('?' * len(ids))})", ids)
        conn.commit()
        done += len(ids)
        progress and progress(done)
        if limit and done >= limit:
            return done
    cache = {}
    while not should_stop():  # ---- images
        rows = conn.execute(
            "SELECT id,source_id,path,ext,size FROM files WHERE embedded=0 AND kind='image' AND ext IN ('jpg','jpeg','png','webp','bmp','gif','tif','tiff') LIMIT ?",
            (16,)).fetchall()
        if not rows:
            break
        ims, ok, bad = [], [], []
        for r in rows:
            if r["size"] > MAX_IMG_BYTES:
                bad.append(r["id"])
                continue
            try:
                src = cache.get(r["source_id"]) or cache.setdefault(r["source_id"], srcmod.load(conn, r["source_id"]))
                with src.fetch(r["path"]) as local:
                    ims.append(_load_image(local))
                ok.append(r["id"])
            except Exception:
                bad.append(r["id"])
        if ims:
            vecs = _model(IMG_MODEL).encode(ims, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
            delete_vectors(conn, ok)
            conn.executemany("INSERT INTO vec_img(file_id, embedding) VALUES (?,?)", [(i, _blob(v)) for i, v in zip(ok, vecs)])
            conn.execute(f"UPDATE files SET embedded=1 WHERE id IN ({','.join('?' * len(ok))})", ok)
        if bad:
            conn.execute(f"UPDATE files SET embedded=2 WHERE id IN ({','.join('?' * len(bad))})", bad)
        conn.commit()
        done += len(rows)
        progress and progress(done)
        if limit and done >= limit:
            break
    return done
