import os
from datetime import datetime

import pytest

from me3 import crawler, db, extract, nlq, search, sources


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "files"
    (root / "uni").mkdir(parents=True)
    (root / "uni" / "fee_receipt.txt").write_text("Semester 4 tuition fee receipt amount 45000 rupees")
    (root / "uni" / "notes.md").write_text("Lecture notes on thermodynamics")
    (root / "IMG_0001.jpg").write_bytes(b"\xff\xd8" + os.urandom(100))
    (root / "big.bin").write_bytes(b"0" * 2_000_000)
    conn = db.connect(tmp_path / "t.db")
    sid = sources.add_source(conn, "local", str(root))
    return conn, sources.load(conn, sid), root


def test_scan_extract_search(env):
    conn, src, root = env
    st = crawler.scan(conn, src)
    assert st["new"] == 4
    extract.run_pending(conn)
    r = search.search(conn, "tuition receipt")
    assert r["results"][0]["name"] == "fee_receipt.txt"
    assert "<mark>" in r["results"][0]["snippet"]
    assert search.search(conn, "photos")["results"][0]["kind"] == "image"  # kind from NL


def test_incremental_and_delete(env):
    conn, src, root = env
    crawler.scan(conn, src)
    assert crawler.scan(conn, src)["same"] == 4
    (root / "uni" / "notes.md").write_text("changed content about entropy")
    (root / "big.bin").unlink()
    st = crawler.scan(conn, src)
    assert st["changed"] == 1 and st["removed"] == 1
    extract.run_pending(conn)
    assert search.search(conn, "entropy")["total"] == 1


def test_index_path_watcher_logic(env):
    conn, src, root = env
    crawler.scan(conn, src)
    new = root / "uni" / "new_file.txt"
    new.write_text("hello zebra")
    crawler.index_path(conn, src, str(new))
    extract.run_pending(conn)
    assert search.search(conn, "zebra")["total"] == 1
    crawler.index_path(conn, src, str(root / "uni"))  # dir removed-style check
    import shutil
    shutil.rmtree(root / "uni")
    crawler.index_path(conn, src, str(root / "uni"))
    assert search.search(conn, "zebra")["total"] == 0


def test_filters(env):
    conn, src, root = env
    crawler.scan(conn, src)
    assert search.search(conn, "", {"min_size": 1_000_000})["total"] == 1
    assert search.search(conn, "larger than 1mb")["results"][0]["name"] == "big.bin"
    assert search.search(conn, "", {"kinds": ["image"]})["total"] == 1


def test_nlq():
    now = datetime(2026, 11, 23)
    text, f = nlq.parse("the fee receipt from last semester", now)
    assert text == "fee receipt" and "after" in f and "before" in f
    text, f = nlq.parse("photos from the Goa beach trip", now)
    assert f["kinds"] == ["image"] and text == "goa beach trip"
    text, f = nlq.parse("pdf invoices larger than 5 MB in march 2024", now)
    assert f["exts"] == ["pdf"] and f["min_size"] == 5 * 1024**2
    assert datetime.fromtimestamp(f["after"]) == datetime(2024, 3, 1)
    text, f = nlq.parse("videos last 3 months", now)
    assert f["kinds"] == ["video"] and f["after"] < now.timestamp()
