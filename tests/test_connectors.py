import socket
from pathlib import Path

import pytest

from me3 import crawler, db, extract, search, sources
from me3.connectors.gdrive import GDriveSource

ROOT = Path(__file__).resolve().parents[1]


class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class FakeDrive:
    """Minimal stand-in for googleapiclient's Drive v3 service."""
    FILES = [
        {"id": "f1", "name": "Documents", "mimeType": "application/vnd.google-apps.folder", "parents": ["root1"]},
        {"id": "d1", "name": "Fee receipt sem5", "mimeType": "application/vnd.google-apps.document", "parents": ["f1"], "modifiedTime": "2025-08-14T10:00:00Z"},
        {"id": "p1", "name": "trip.jpg", "mimeType": "image/jpeg", "size": "12345", "parents": ["f1"], "modifiedTime": "2025-01-02T10:00:00Z"},
        {"id": "x1", "name": "A form", "mimeType": "application/vnd.google-apps.form", "parents": ["f1"]},
    ]
    def files(self): return self
    def list(self, **kw): return _Exec({"files": self.FILES})
    def about(self): return self
    def get(self, **kw): return _Exec({"user": {}})


def test_gdrive_walk_paths_and_types():
    src = GDriveSource(1, service=FakeDrive())
    ents = {e.name: e for e in src.walk()}
    assert set(ents) == {"Fee receipt sem5.gdoc", "trip.jpg"}  # folder + unsupported form skipped
    assert ents["trip.jpg"].path == "/Documents/trip.jpg#p1" and ents["trip.jpg"].size == 12345
    assert src._ids[ents["Fee receipt sem5.gdoc"].path][1].endswith("document")


def test_gdrive_indexes_through_crawler(tmp_path):
    conn = db.connect(tmp_path / "g.db")
    sid = sources.add_source(conn, "gdrive", "/", "Drive")
    src = GDriveSource(sid, service=FakeDrive())
    assert crawler.scan(conn, src)["new"] == 2
    assert search.search(conn, "fee receipt", semantic=False)["total"] == 1  # filename match; .gdoc is a document


def _sshd_up():
    try:
        socket.create_connection(("127.0.0.1", 2222), timeout=0.5).close()
        return (ROOT / "data/sshd/client").exists()
    except OSError:
        return False


@pytest.mark.skipif(not _sshd_up(), reason="needs the test sshd on :2222 (see README: SFTP test server)")
def test_sftp_roundtrip(tmp_path):

    conn = db.connect(tmp_path / "s.db")
    cfg = {"host": "127.0.0.1", "port": 2222, "username": __import__("getpass").getuser(), "key_file": str(ROOT / "data/sshd/client")}
    sid = sources.add_source(conn, "sftp", str(ROOT / "data/sftp_demo"), "nas", cfg)
    src = sources.load(conn, sid)
    src.test()
    assert crawler.scan(conn, src)["new"] >= 2
    extract.run_pending(conn)
    assert search.search(conn, "tuition", semantic=False)["total"] >= 1
