"""Parsing and normalization for raw email text (proposal: "Parsing and normalization").

Pipeline, in order:
  1. MIME decode (Python `email`): headers, multipart, quoted-printable, base64, charsets.
     Rows that are not RFC-822 messages (plain bodies, as in D1) pass through unchanged,
     except for a stray quoted-printable pass when the text clearly carries =XX escapes.
  2. Strip HTML / CSS / script.
  3. Unicode NFKC.
  4. Normalise case (lower) and whitespace; collapse '- - - -' style separator runs.
  5. URLs -> domain token (``url_<domain>``) and a URL count.
  6. Mask emails -> ``<email>``, phones -> ``<phone>``, numbers -> ``<num>``.
  7. Drop empty / placeholder / under-MIN_TOKENS rows.
  8. Truncate to MAX_CHARS characters.

`normalize_text` returns (text, n_urls, status) so callers can count drops.
Everything is deterministic and dependency-light (bs4 optional, falls back to regex).
"""
from __future__ import annotations

import email
import html
import quopri
import re
import unicodedata
from email import policy

try:  # optional, better HTML handling
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

MIN_TOKENS = 10
MAX_CHARS = 5000
PLACEHOLDERS = {"empty", "nan", "none", "null", ""}

_HEADER_START = re.compile(
    r"\A\s*(received|from|return-path|delivered-to|mime-version|content-type|subject|date|x-[\w-]+|message-id):",
    re.I,
)
_HTML_HINT = re.compile(r"<\s*(html|body|div|table|span|p|br|a|style|script|font|td|tr|img)\b", re.I)
_QP_HINT = re.compile(r"=(?:[0-9A-F]{2}|\r?\n)")
_URL = re.compile(r"(?i)\b(?:https?://|ftp://|www\.)[^\s<>\"')\]]+")
_EMAIL = re.compile(r"(?i)\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE = re.compile(r"(?<![\w])(?:\+?\d{1,2}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?![\w])")
_NUM = re.compile(r"(?<![a-z_])\d[\d,.:/-]*\d|\d")
_SEP = re.compile(r"(?:[-_=*#~/.]\s?){4,}")
_WS = re.compile(r"\s+")
_TAGLIKE = re.compile(r"<(?!email>|phone>|num>)[^>\n]{0,200}>")


def _decode_mime(raw: str) -> str:
    """Decode MIME/QP/base64 when the text looks like an RFC-822 message; else light QP fix."""
    if _HEADER_START.match(raw) or re.search(r"(?im)^content-(type|transfer-encoding):", raw[:4000]):
        try:
            msg = email.message_from_string(raw, policy=policy.default)
            parts, subject = [], msg.get("subject")
            if subject:
                parts.append(str(subject))
            html_parts = []
            for part in msg.walk():
                if part.is_multipart():
                    continue
                ctype = part.get_content_type()
                if ctype not in ("text/plain", "text/html"):
                    continue  # skip attachments / images
                try:
                    payload = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True)
                    payload = payload.decode(part.get_content_charset() or "utf-8", "replace") if payload else ""
                (html_parts if ctype == "text/html" else parts).append(str(payload))
            body = "\n".join(parts) if parts else ""
            if not body.strip():
                body = "\n".join(html_parts)
            elif html_parts and not any(p.strip() for p in parts[1:] if p):
                body += "\n" + "\n".join(html_parts)
            if body.strip():
                return body
        except Exception:
            pass
    # Not a message: undo stray quoted-printable escapes (=3D, =20, soft line breaks)
    if len(_QP_HINT.findall(raw)) >= 2:
        try:
            return quopri.decodestring(raw.encode("utf-8", "ignore")).decode("utf-8", "replace")
        except Exception:
            return raw
    return raw


def _strip_html(text: str) -> str:
    if not _HTML_HINT.search(text):
        return text
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(text, "lxml")
            for t in soup(["script", "style", "head", "noscript"]):
                t.decompose()
            # keep link targets: they carry the URL-domain signal
            for a in soup.find_all("a", href=True):
                a.append(" " + a["href"] + " ")
            for img in soup.find_all("img", src=True):
                img.append(" " + img["src"] + " ")
            return soup.get_text(" ")
        except Exception:
            pass
    text = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", text)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def _domain_token(url: str) -> str:
    u = re.sub(r"(?i)^(?:https?://|ftp://)", "", url)
    host = re.split(r"[/?#:]", u, maxsplit=1)[0].lower().removeprefix("www.")
    host = re.sub(r"[^a-z0-9.-]", "", host).strip(".")
    return "url_" + host.replace(".", "_").replace("-", "_") if host else "url_unknown"


def caps_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are upper-case (computed BEFORE lower-casing)."""
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def normalize_full(raw) -> dict:
    """Like normalize_text but also returns raw-derived formatting features (caps_ratio, raw_len)."""
    out = {"text": "", "n_urls": 0, "status": "empty", "caps_ratio": 0.0, "raw_len": 0}
    if isinstance(raw, str):
        out["raw_len"] = len(raw)
    text, n, st = normalize_text(raw, _caps_sink=out)
    out.update(text=text, n_urls=n, status=st)
    return out


def normalize_text(raw, _caps_sink: dict | None = None) -> tuple[str, int, str]:
    """Return (normalized_text, n_urls, status). status in {'ok','empty','short'}."""
    if raw is None or not isinstance(raw, str):
        return "", 0, "empty"
    if raw.strip().lower() in PLACEHOLDERS:
        return "", 0, "empty"
    raw = raw[:2_000_000]  # guard against multi-MB attachments / base64 blobs
    text = _decode_mime(raw)
    text = _strip_html(text)
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = _TAGLIKE.sub(" ", text)
    if _caps_sink is not None:
        _caps_sink["caps_ratio"] = round(caps_ratio(text), 4)
    text = text.lower()
    n_urls = 0

    def _url_sub(m):
        nonlocal n_urls
        n_urls += 1
        return " " + _domain_token(m.group(0)) + " "

    text = _URL.sub(_url_sub, text)
    text = _EMAIL.sub(" <email> ", text)
    text = _PHONE.sub(" <phone> ", text)
    text = _NUM.sub(" <num> ", text)
    text = _SEP.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    text = text[:MAX_CHARS].rstrip()
    if len(text.split()) < MIN_TOKENS:
        return text, n_urls, "short"
    return text, n_urls, "ok"
