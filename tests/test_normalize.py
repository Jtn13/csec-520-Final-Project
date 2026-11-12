from src.normalize import normalize_text

def test_mime_qp_base64_html():
    import base64
    b64 = base64.b64encode(b"<html><body><p>Verify your account at <a href='http://Evil-Bank.example.com/login?x=1'>here</a> now. Call 555-123-4567 or mail a@b.com, amount 1,200.50 dollars today please</p><script>x=1</script></body></html>").decode()
    raw = "From: a@b.com\nSubject: Urgent =?utf-8?q?Notice?=\nMIME-Version: 1.0\nContent-Type: text/html; charset=utf-8\nContent-Transfer-Encoding: base64\n\n" + b64
    t, n, st = normalize_text(raw)
    assert st == "ok" and n == 1
    assert "url_evil_bank_example_com" in t and "<phone>" in t and "<email>" in t and "<num>" in t
    assert "script" not in t and "x=1" not in t

def test_qp_plain_and_nfkc():
    t, n, st = normalize_text("ＦＲＥＥ money=20now click=3D here to claim your prize today and win big money now friends")
    assert "free" in t and "=3d" not in t and st == "ok"

def test_empty_and_short():
    assert normalize_text("empty")[2] == "empty"
    assert normalize_text(None)[2] == "empty"
    assert normalize_text("too few words here")[2] == "short"

def test_truncate():
    t, _, st = normalize_text("word " * 5000)
    assert len(t) <= 5000
