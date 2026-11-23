"""SFTP source (paramiko): browse/index a remote server or NAS next to local folders.

config: {"host", "port"=22, "username", "password"? , "key_file"? , "known_hosts"? }
Security: with "known_hosts" the server key is verified; otherwise the key is auto-accepted on first use (TOFU) - fine for a
LAN NAS, set known_hosts for anything else. Prefer key_file over password (the config is stored in the local SQLite DB only).
"""
import contextlib
import os
import posixpath
import stat
import tempfile
import threading

from ..sources import Entry
from ..util import IGNORE_DIRS


class SftpSource:
    kind = "sftp"
    watchable = False  # no inotify over SFTP; the watcher falls back to periodic incremental rescans

    def __init__(self, id: int, root: str, name: str = "", config: dict | None = None):
        self.id, self.root, self.name, self.config = id, root or "/", name or root, config or {}
        self._tl = threading.local()

    # --- connection (one per thread; paramiko clients are not thread-safe)
    def _sftp(self):
        c = getattr(self._tl, "sftp", None)
        if c is not None:
            try:
                c.stat(".")
                return c
            except Exception:
                self._tl.sftp = None
        import paramiko

        cfg = self.config
        ssh = paramiko.SSHClient()
        if cfg.get("known_hosts"):
            ssh.load_host_keys(cfg["known_hosts"])
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            cfg["host"], port=int(cfg.get("port", 22)), username=cfg.get("username"), password=cfg.get("password") or None,
            key_filename=cfg.get("key_file") or None, timeout=15, allow_agent=False, look_for_keys=False,
        )
        self._tl.ssh, self._tl.sftp = ssh, ssh.open_sftp()
        return self._tl.sftp

    def test(self) -> None:
        """Raise if the server or root folder is not reachable."""
        self._sftp().listdir(self.root)

    # --- Source interface
    def walk(self, start: str | None = None):
        sftp = self._sftp()
        stack = [start or self.root]
        while stack:
            d = stack.pop()
            try:
                items = sftp.listdir_attr(d)
            except OSError:
                continue
            for a in items:
                p = posixpath.join(d, a.filename)
                if stat.S_ISDIR(a.st_mode or 0):
                    if a.filename not in IGNORE_DIRS:
                        stack.append(p)
                elif stat.S_ISREG(a.st_mode or 0):
                    yield Entry(p, a.filename, a.st_size or 0, float(a.st_mtime or 0))

    def stat(self, path: str) -> Entry | None:
        try:
            a = self._sftp().stat(path)
        except OSError:
            return None
        if stat.S_ISDIR(a.st_mode or 0):
            return Entry(path, posixpath.basename(path), 0, float(a.st_mtime or 0), True)
        return Entry(path, posixpath.basename(path), a.st_size or 0, float(a.st_mtime or 0))

    @contextlib.contextmanager
    def fetch(self, path: str):
        """Download to a temp file for extraction/embedding, delete afterwards."""
        fd, tmp = tempfile.mkstemp(suffix="_" + posixpath.basename(path), dir=os.environ.get("ME3_TMP"))
        os.close(fd)
        try:
            self._sftp().get(path, tmp)
            yield tmp
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
