"""End-to-end SFTP connector test against an in-process paramiko SFTP server (no sshd needed)."""
import os
import socket
import threading

import paramiko
import pytest

from me3 import crawler, db, extract, search, sources


class _Auth(paramiko.ServerInterface):
    def check_auth_password(self, u, p):
        return paramiko.AUTH_SUCCESSFUL if (u, p) == ("t", "t") else paramiko.AUTH_FAILED

    def get_allowed_auths(self, u):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED


def _server(root):
    class Handle(paramiko.SFTPServerInterface):
        def _p(self, p):
            return os.path.join(root, p.lstrip("/"))

        def list_folder(self, path):
            return [paramiko.SFTPAttributes.from_stat(os.stat(os.path.join(self._p(path), n)), n) for n in os.listdir(self._p(path))]

        def stat(self, path):
            try:
                return paramiko.SFTPAttributes.from_stat(os.stat(self._p(path)))
            except OSError as e:
                return paramiko.SFTPServer.convert_errno(e.errno)

        lstat = stat

        def open(self, path, flags, attr):
            try:
                f = open(self._p(path), "rb")
            except OSError as e:
                return paramiko.SFTPServer.convert_errno(e.errno)
            h = paramiko.SFTPHandle(flags)
            h.filename, h.readfile = self._p(path), f
            return h

    key = paramiko.RSAKey.generate(2048)
    ls = socket.socket()
    ls.bind(("127.0.0.1", 0))
    ls.listen(5)

    def loop():
        while True:
            try:
                c, _ = ls.accept()
            except OSError:
                return
            t = paramiko.Transport(c)
            t.add_server_key(key)
            t.set_subsystem_handler("sftp", paramiko.SFTPServer, Handle)
            t.start_server(server=_Auth())

    threading.Thread(target=loop, daemon=True).start()
    return ls


@pytest.fixture
def sftp_env(tmp_path):
    remote = tmp_path / "remote"
    (remote / "docs").mkdir(parents=True)
    (remote / "docs" / "lease.txt").write_text("rental lease agreement quokka clause")
    (remote / "photo.jpg").write_bytes(b"\xff\xd8" + b"x" * 50)
    ls = _server(str(remote))
    conn = db.connect(tmp_path / "t.db")
    cfg = {"host": "127.0.0.1", "port": ls.getsockname()[1], "username": "t", "password": "t"}
    sid = sources.add_source(conn, "sftp", "/", config=cfg)
    yield conn, sources.load(conn, sid)
    ls.close()


def test_sftp_scan_extract_search(sftp_env):
    conn, src = sftp_env
    src.test()
    assert crawler.scan(conn, src)["new"] == 2
    extract.run_pending(conn)
    assert search.search(conn, "quokka")["results"][0]["name"] == "lease.txt"
