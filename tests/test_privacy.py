from me3 import privacy


def test_regex_identifiers():
    t = "PAN ABCDE1234F, Aadhaar 2345 6789 0123, IFSC HDFC0001234, phone +91 98765 43210, mail rahul.s@example.com, pay me@okaxis"
    r = privacy.redact(t, use_presidio=False)
    for leak in ("ABCDE1234F", "2345 6789 0123", "HDFC0001234", "98765 43210", "rahul.s@example.com", "me@okaxis"):
        assert leak not in r.text, leak
    assert {"IN_PAN", "IN_AADHAAR", "IN_IFSC", "PHONE", "EMAIL", "UPI_ID"} <= set(r.counts)


def test_card_needs_luhn():
    assert "<CARD_1>" in privacy.redact("card 4111 1111 1111 1111", use_presidio=False).text
    assert "<CARD" not in privacy.redact("order id 1234 5678 9012 3456", use_presidio=False).text


def test_secrets_and_stable_placeholders():
    r = privacy.redact("password: hunter2 and again a@b.com then a@b.com", use_presidio=False)
    assert "hunter2" not in r.text and r.text.count("<EMAIL_1>") == 2


def test_presidio_names():
    r = privacy.redact("Meeting with Priya Nair about the invoice.")
    assert "Priya Nair" not in r.text


def test_payload_strips_home_and_pii():
    import os
    home = os.path.expanduser("~")
    p = privacy.prepare_payload([{"path": f"{home}/Documents/rahul.s@example.com_statement.pdf", "name": "rahul.s@example.com_statement.pdf",
                                  "kind": "document", "ext": "pdf", "size": 2048, "modified": "2025-03-01 10:00",
                                  "snippet": "Account holder Priya Nair PAN ABCDE1234F balance"}])
    s = str(p)
    assert home not in s and "rahul.s@example.com" not in s and "ABCDE1234F" not in s
    assert p["items"][0]["year"] == "2025" and p["redacted"]


def test_password_phrasings():
    leaks = {"my password is hunter2": "hunter2", "passwd hunter2": "hunter2", "pass: qwerty": "qwerty", "Password - S3cret!x": "S3cret!x",
             "PIN: 4821": "4821", "the wifi password is hunter2.": "hunter2", "password for gmail is Abc@12345": "Abc@12345",
             "OTP is 482910": "482910", "pwd=abc123": "abc123", "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789": "ghp_"}
    for text, secret in leaks.items():
        out = privacy.redact(text, use_presidio=False).text
        assert secret not in out and "<SECRET_1>" in out, (text, out)
    assert privacy.redact("password: hunter2", use_presidio=False).text == "password: <SECRET_1>"  # keyword stays readable
    for ok in ("please reset my password tomorrow", "I will pass the exam", "forgot password? click here", "pin the tab"):
        assert privacy.redact(ok, use_presidio=False).text == ok
