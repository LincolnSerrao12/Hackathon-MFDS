"""Background indexing manager: scan -> extract -> watch, one thread per source, low CPU priority."""
import threading
import time

from . import crawler, db, extract, sources
from .watcher import Watcher, lower_priority


class Indexer:
    def __init__(self):
        self.status: dict[int, dict] = {}
        self.watchers: dict[int, Watcher] = {}
        self.stop_evt = threading.Event()

    def start_source(self, source_id: int, watch: bool = True):
        if self.status.get(source_id, {}).get("state") in ("scanning", "extracting"):
            return
        self.status[source_id] = {"state": "queued", "scanned": 0, "extracted": 0, "stats": {}, "started": time.time()}
        threading.Thread(target=self._run, args=(source_id, watch), daemon=True, name=f"index-{source_id}").start()

    def _run(self, sid: int, watch: bool):
        lower_priority()
        st = self.status[sid]
        try:
            conn = db.connect()
            src = sources.load(conn, sid)
            st["state"] = "scanning"
            st["stats"] = crawler.scan(conn, src, progress=lambda n: st.__setitem__("scanned", n), should_stop=self.stop_evt.is_set)
            st["state"] = "extracting"
            extract.run_pending(conn, progress=lambda n: st.__setitem__("extracted", n), should_stop=self.stop_evt.is_set)
            st["state"] = "idle"
            st["finished"] = time.time()
            if watch and sid not in self.watchers:
                w = self.watchers[sid] = Watcher(src)
                w.start()
        except Exception as e:  # keep the app alive, surface the error in status
            st["state"], st["error"] = "error", repr(e)

    def resume_all(self):
        """On server start: rescan + watch every registered source (catches changes made while offline)."""
        for s in sources.load_all(db.connect()):
            self.start_source(s.id)

    def shutdown(self):
        self.stop_evt.set()
        for w in self.watchers.values():
            w.stop()

    def snapshot(self):
        out = {}
        for sid, st in self.status.items():
            d = dict(st)
            d["watching"] = self.watchers[sid].mode if sid in self.watchers else None
            out[sid] = d
        return out


indexer = Indexer()
