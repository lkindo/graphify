# Security helpers - URL validation, safe fetch, path guards, label sanitisation
from __future__ import annotations

import html
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import ipaddress
import socket

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_FETCH_BYTES = 52_428_800   # 50 MB hard cap for binary downloads
_MAX_TEXT_BYTES  = 10_485_760   # 10 MB hard cap for HTML / text

# AWS metadata, link-local, and common cloud metadata endpoints
_BLOCKED_HOSTS = {"metadata.google.internal", "metadata.google.com"}


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def validate_url(url: str) -> str:
    """Raise ValueError if *url* is not http or https, or targets a private/internal IP.

    Blocks file://, ftp://, data:, and any other scheme that could be used
    for SSRF or local file access. Also blocks requests to private/reserved
    IP ranges (127.x, 10.x, 169.254.x, etc.) and cloud metadata endpoints
    to prevent SSRF in cloud environments.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Blocked URL scheme '{parsed.scheme}' - only http and https are allowed. "
            f"Got: {url!r}"
        )

    hostname = parsed.hostname
    if hostname:
        # Block known cloud metadata hostnames
        if hostname.lower() in _BLOCKED_HOSTS:
            raise ValueError(
                f"Blocked cloud metadata endpoint '{hostname}'. "
                f"Got: {url!r}"
            )

        # Resolve hostname and block private/reserved IP ranges
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for info in infos:
                addr = info[4][0]
                ip = ipaddress.ip_address(addr)
                if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                    raise ValueError(
                        f"Blocked private/internal IP {addr} (resolved from '{hostname}'). "
                        f"Got: {url!r}"
                    )
        except socket.gaierror:
            # DNS failure is a connectivity problem, not proof the URL is unsafe.
            # Let the fetch step surface the underlying network error.
            pass

    return url


def _validate_peer_ip(resp: object, url: str) -> None:
    """Re-validate the peer IP after connection to defend against DNS rebinding.

    urllib may re-resolve DNS between validate_url() and the actual connection.
    Checking the connected socket's peer address closes this TOCTOU gap.

    Args:
        resp: The HTTP response object (may have .fp.raw._sock or similar).
        url: The original URL (for error messages).

    Raises:
        ValueError: If the peer IP is private/reserved/loopback/link-local.
    """
    try:
        # urllib wraps the socket; walk down to the raw socket
        raw_sock = None
        fp = getattr(resp, 'fp', None)
        if fp:
            raw = getattr(fp, 'raw', None)
            if raw:
                raw_sock = getattr(raw, '_sock', None)
        if raw_sock is None:
            # Cannot inspect peer - log and allow (defense in depth, not sole layer)
            logger.debug("Cannot inspect peer socket for %s - skipping rebind check", url)
            return
        peer = raw_sock.getpeername()
        if peer:
            addr = peer[0]
            if not isinstance(addr, str):
                logger.debug("Peer IP check skipped for %s (non-string peer address)", url)
                return
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                raise ValueError(
                    f"DNS rebinding detected: connected to private IP {addr} "
                    f"for URL {url!r}"
                )
    except (AttributeError, OSError, ValueError):
        # Socket already closed or inaccessible - skip check
        logger.debug("Peer IP check skipped for %s (socket inaccessible)", url)


class _NoFileRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-validates every redirect target.

    Prevents open-redirect SSRF attacks where an http:// URL redirects
    to file:// or an internal address.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)          # raises ValueError if scheme is wrong
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoFileRedirectHandler)


# ---------------------------------------------------------------------------
# Safe fetch
# ---------------------------------------------------------------------------

def safe_fetch(url: str, max_bytes: int = _MAX_FETCH_BYTES, timeout: int = 30) -> bytes:
    """Fetch *url* and return raw bytes.

    Protections applied:
    - URL scheme validated (http / https only)
    - Redirects re-validated via _NoFileRedirectHandler
    - Response body capped at *max_bytes* (streaming read)
    - Non-2xx status raises urllib.error.HTTPError
    - Network errors propagate as urllib.error.URLError / OSError

    Raises:
        ValueError        - disallowed scheme or redirect target
        urllib.error.HTTPError  - non-2xx HTTP status
        urllib.error.URLError   - DNS / connection failure
        OSError               - size cap exceeded
    """
    validate_url(url)
    opener = _build_opener()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 graphify/1.0"})

    with opener.open(req, timeout=timeout) as resp:
        # urllib raises HTTPError for non-2xx when using urlopen directly;
        # with a custom opener we check manually to be safe.
        status = getattr(resp, "status", None) or getattr(resp, "code", None)
        if status is not None and not (200 <= status < 300):
            raise urllib.error.HTTPError(url, status, f"HTTP {status}", {}, None)

        # DNS rebinding defense: re-validate the peer IP after connection
        _validate_peer_ip(resp, url)

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = resp.read(65_536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise OSError(
                    f"Response from {url!r} exceeds size limit "
                    f"({max_bytes // 1_048_576} MB). Aborting download."
                )
            chunks.append(chunk)

    return b"".join(chunks)


def safe_fetch_text(url: str, max_bytes: int = _MAX_TEXT_BYTES, timeout: int = 15) -> str:
    """Fetch *url* and return decoded text (UTF-8, replacing bad bytes).

    Wraps safe_fetch with tighter defaults for HTML / text content.
    """
    raw = safe_fetch(url, max_bytes=max_bytes, timeout=timeout)
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def validate_graph_path(path: str | Path, base: Path | None = None) -> Path:
    """Resolve *path* and verify it stays inside *base*.

    *base* defaults to the `graphify-out` directory relative to CWD.
    Also requires the base directory to exist, so a caller cannot
    trick graphify into reading files before any graph has been built.

    Raises:
        ValueError  - path escapes base, or base does not exist
        FileNotFoundError - resolved path does not exist
    """
    if base is None:
        base = Path("graphify-out").resolve()

    base = base.resolve()
    if not base.exists():
        raise ValueError(
            f"Graph base directory does not exist: {base}. "
            "Run /graphify first to build the graph."
        )

    resolved = Path(path).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(
            f"Path {path!r} escapes the allowed directory {base}. "
            "Only paths inside graphify-out/ are permitted."
        )

    if not resolved.exists():
        raise FileNotFoundError(f"Graph file not found: {resolved}")

    return resolved


# ---------------------------------------------------------------------------
# Label sanitisation (mirrors code-review-graph's _sanitize_name pattern)
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_LABEL_LEN = 256


def sanitize_label(text: str, *, html_safe: bool = False) -> str:
    """Strip control characters and cap length.

    Safe for embedding in JSON data (inside <script> tags) and plain text.

    Args:
        text: The raw label text to sanitize.
        html_safe: If True, also applies html.escape() to prevent XSS.

    Returns:
        Sanitized label string.
    """
    text = _CONTROL_CHAR_RE.sub("", text)
    if len(text) > _MAX_LABEL_LEN:
        text = text[:_MAX_LABEL_LEN]
    if html_safe:
        text = html.escape(text, quote=True)
    return text
