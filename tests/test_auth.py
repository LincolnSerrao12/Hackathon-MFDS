import time

from me3 import auth


def test_cookie_signing_roundtrip_and_tamper():
    tok = auth.sign({"email": "a@b.c", "exp": time.time() + 60})
    assert auth.unsign(tok)["email"] == "a@b.c"
    assert auth.unsign(tok[:-2] + "00") is None
    assert auth.unsign(auth.sign({"email": "a@b.c", "exp": time.time() - 1})) is None
    assert auth.unsign(None) is None


def test_allowlist_env(monkeypatch):
    monkeypatch.setenv("ME3_ALLOWED_EMAILS", "ok@x.com")
    assert auth._allowed("OK@x.com") and not auth._allowed("evil@x.com")
