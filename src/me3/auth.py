"""Sign in with Google for the web UI.

Uses the same Desktop-type OAuth client as the Drive connector (client_secret_*.json); Google allows loopback
redirects (http://localhost:<port>/...) for that client type, so nothing extra needs registering.
Only identity scopes (openid email profile) are requested here; Drive access stays a separate consent (gdrive-auth).

Who may sign in: ME3_ALLOWED_EMAILS (comma separated) if set; otherwise the first Google account to sign in becomes
the owner (stored in data/owner.txt) and nobody else is let in.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from . import db
from .connectors.gdrive import find_client_secret

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")  # loopback http only; see _host_ok
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")   # Google may return scopes in a different form

STATIC = Path(__file__).resolve().parent / "static"
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
COOKIE, STATE_COOKIE = "me3_session", "me3_oauth"
SESSION_TTL = 7 * 24 * 3600
OWNER_FILE = db.ROOT / "data" / "owner.txt"
SECRET_FILE = db.ROOT / "data" / ".session_secret"
PUBLIC = ("/login", "/auth/", "/favicon.ico")

router = APIRouter()


def _secret() -> bytes:
    if not SECRET_FILE.exists():
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(secrets.token_hex(32))
        SECRET_FILE.chmod(0o600)
    return SECRET_FILE.read_text().strip().encode()


def sign(data: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    mac = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def unsign(token: str | None) -> dict | None:
    try:
        body, mac = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(mac, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()):
            return None
        data = json.loads(base64.urlsafe_b64decode(body))
        return data if data.get("exp", 0) > time.time() else None
    except Exception:  # noqa: BLE001
        return None


def current_user(request: Request) -> dict | None:
    return unsign(request.cookies.get(COOKIE))


def _allowed(email: str) -> bool:
    email = email.lower()
    env = [e.strip().lower() for e in os.environ.get("ME3_ALLOWED_EMAILS", "").split(",") if e.strip()]
    if env:
        return email in env
    if OWNER_FILE.exists():
        return OWNER_FILE.read_text().strip().lower() == email
    OWNER_FILE.write_text(email)  # first sign-in claims the app
    OWNER_FILE.chmod(0o600)
    return True


def _host_ok(request: Request) -> bool:
    return (request.url.hostname or "") in ("localhost", "127.0.0.1")


def _flow(request: Request, state: str | None = None):
    from google_auth_oauthlib.flow import Flow

    base = f"{request.url.scheme}://{request.url.netloc}"
    return Flow.from_client_secrets_file(str(find_client_secret()), scopes=SCOPES, redirect_uri=f"{base}/auth/callback", state=state)


def _cookie(resp, name, value, max_age):
    resp.set_cookie(name, value, max_age=max_age, httponly=True, samesite="lax", path="/")


def _fail(request: Request, msg: str):
    return RedirectResponse(f"/login?error={msg}", status_code=303)


@router.get("/login")
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC / "login.html")


@router.get("/auth/start")
def start(request: Request):
    if not _host_ok(request):
        return _fail(request, "Open the app via http://localhost:8765")
    try:
        flow = _flow(request)
    except RuntimeError as e:
        return _fail(request, str(e))
    flow.code_verifier = secrets.token_urlsafe(64)
    url, state = flow.authorization_url(access_type="online", prompt="select_account", include_granted_scopes="false")
    resp = RedirectResponse(url, status_code=303)
    _cookie(resp, STATE_COOKIE, sign({"s": state, "v": flow.code_verifier, "exp": time.time() + 600}), 600)
    return resp


@router.get("/auth/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return _fail(request, "Google sign-in was cancelled or denied")
    saved = unsign(request.cookies.get(STATE_COOKIE))
    if not saved or not code or not secrets.compare_digest(saved["s"], state):
        return _fail(request, "Sign-in session expired, please try again")
    try:
        from google.auth.transport import requests as greq
        from google.oauth2 import id_token

        flow = _flow(request, state)
        flow.code_verifier = saved["v"]
        flow.fetch_token(code=code)
        info = id_token.verify_oauth2_token(flow.credentials.id_token, greq.Request(), flow.client_config["client_id"], clock_skew_in_seconds=10)
    except Exception as e:  # noqa: BLE001
        return _fail(request, f"Google sign-in failed: {type(e).__name__}")
    email = info.get("email", "")
    if not info.get("email_verified") or not _allowed(email):
        return _fail(request, f"{email or 'This account'} is not allowed to use this app")
    user = {"email": email, "name": info.get("name", email), "picture": info.get("picture", ""), "exp": time.time() + SESSION_TTL}
    resp = RedirectResponse("/", status_code=303)
    _cookie(resp, COOKIE, sign(user), SESSION_TTL)
    resp.delete_cookie(STATE_COOKIE, path="/")
    return resp


@router.post("/auth/logout")
@router.get("/auth/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE, path="/")
    return resp


@router.get("/api/me")
def me(request: Request):
    u = current_user(request)
    return {"email": u["email"], "name": u["name"], "picture": u["picture"]} if u else JSONResponse({"detail": "not signed in"}, 401)


async def require_login(request: Request, call_next):
    path = request.url.path
    if path.startswith(PUBLIC) or current_user(request):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Sign in with Google first"}, status_code=401)
    return RedirectResponse("/login", status_code=303)
