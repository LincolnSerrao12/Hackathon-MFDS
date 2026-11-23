"""Google Drive source (read-only OAuth). Setup, once:
 1. Google Cloud Console -> APIs & Services -> enable "Google Drive API"
 2. Credentials -> Create OAuth client ID (type: Desktop app) -> download JSON -> save as <project>/credentials.json
 3. OAuth consent screen: add your Google account as a test user
 4. Run:  python -m me3 gdrive-auth      (opens a browser once; stores <project>/token.json)
 5. Add the source in the UI (kind=gdrive, root="/") or:  python -m me3 add-gdrive
Google-native files (Docs/Sheets/Slides) are exported as text for indexing; other files are downloaded to a temp file on demand.
The `service` argument allows injecting a fake Drive client for tests.
"""
import contextlib
import io
import os
import tempfile
from datetime import datetime

from .. import db
from ..sources import Entry

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
CREDS = db.ROOT / "credentials.json"
TOKEN = db.ROOT / "token.json"
FOLDER = "application/vnd.google-apps.folder"
NATIVE = {  # mime -> (suffix we show, export mime)
    "application/vnd.google-apps.document": (".gdoc", "text/plain"),
    "application/vnd.google-apps.spreadsheet": (".gsheet", "text/csv"),
    "application/vnd.google-apps.presentation": (".gslides", "text/plain"),
}


def authorize() -> None:
    """Interactive one-time OAuth flow; writes token.json."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    os.chmod(TOKEN, 0o600)


def build_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not TOKEN.exists():
        raise RuntimeError("Google Drive not authorised: run `python -m me3 gdrive-auth` first (see connectors/gdrive.py)")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _ts(s: str) -> float:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


class GDriveSource:
    kind = "gdrive"
    watchable = False

    def __init__(self, id: int, root: str = "/", name: str = "", config: dict | None = None, service=None):
        self.id, self.root, self.name, self.config = id, root or "/", name or "Google Drive", config or {}
        self._service = service
        self._ids: dict[str, tuple[str, str]] = {}  # path -> (file id, mime)

    @property
    def svc(self):
        if self._service is None:
            self._service = build_service()
        return self._service

    def test(self) -> None:
        self.svc.about().get(fields="user").execute()

    def _list_all(self):
        token = None
        while True:
            r = self.svc.files().list(
                q="trashed=false", pageSize=1000, pageToken=token,
                fields="nextPageToken, files(id,name,mimeType,size,modifiedTime,parents)",
            ).execute()
            yield from r.get("files", [])
            token = r.get("nextPageToken")
            if not token:
                break

    def walk(self, start: str | None = None):
        files = list(self._list_all())
        by_id = {f["id"]: f for f in files}

        def folder_path(fid, depth=0):
            f = by_id.get(fid)
            if not f or depth > 30:
                return ""
            par = (f.get("parents") or [None])[0]
            return folder_path(par, depth + 1) + "/" + f["name"] if par else "/" + f["name"]

        self._ids.clear()
        for f in files:
            if f["mimeType"] == FOLDER:
                continue
            native = NATIVE.get(f["mimeType"])
            if f["mimeType"].startswith("application/vnd.google-apps.") and not native:
                continue  # forms, drawings, shortcuts...
            par = (f.get("parents") or [None])[0]
            name = f["name"] + (native[0] if native else "")
            path = (folder_path(par) if par else "") + "/" + name + f"#{f['id']}"
            self._ids[path] = (f["id"], f["mimeType"])
            yield Entry(path, name, int(f.get("size") or 0), _ts(f.get("modifiedTime", "")))

    def stat(self, path: str):
        return None  # not used (no watcher); periodic rescans call walk()

    @contextlib.contextmanager
    def fetch(self, path: str):
        fid, mime = self._ids.get(path) or (path.rsplit("#", 1)[-1], "")
        if not mime:
            base = path.rsplit("#", 1)[0]
            mime = next((m for m, (suf, _) in NATIVE.items() if base.endswith(suf)), "")
        suffix = "_" + os.path.basename(path.rsplit("#", 1)[0])
        fd, tmp = tempfile.mkstemp(suffix=suffix, dir=os.environ.get("ME3_TMP"))
        os.close(fd)
        try:
            from googleapiclient.http import MediaIoBaseDownload

            if mime in NATIVE:
                req = self.svc.files().export_media(fileId=fid, mimeType=NATIVE[mime][1])
            else:
                req = self.svc.files().get_media(fileId=fid)
            buf = io.FileIO(tmp, "wb")
            dl = MediaIoBaseDownload(buf, req, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                _, done = dl.next_chunk()
            buf.close()
            yield tmp
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
