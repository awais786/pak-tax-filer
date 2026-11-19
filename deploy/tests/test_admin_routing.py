"""/admin reaches the backend in production (Caddy) and development (Vite) (feature 011, task
T019; FR-025; research R11). Read as text: neither tool runs here."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CADDYFILE = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
VITE = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")


def test_caddy_sends_admin_to_the_backend_before_the_static_files() -> None:
    """Fails if /admin isn't proxied to the backend, or the React app's catch-all comes first
    (it would answer /admin with index.html)."""
    match = re.search(r"handle /admin /admin/\*\s*\{\s*reverse_proxy backend:8000\s*\}", CADDYFILE)
    assert match, "no /admin handle"
    static = CADDYFILE.index("try_files")
    assert match.start() < static


def test_caddy_keeps_its_security_headers() -> None:
    """Fails if adding /admin dropped a security header."""
    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "Referrer-Policy",
        'X-Frame-Options "DENY"',
    ):
        assert header in CADDYFILE, header


def test_vite_proxies_admin_in_development_keeping_the_host() -> None:
    """Fails if /admin on the dev server (localhost:5173) doesn't reach the backend, or reaches it
    with the Host rewritten: the admin library builds absolute links from the Host, so they would
    point at backend:8000, which the browser can't reach (found by the e2e test)."""
    # A regex key, so it matches /admin and /admin/... only, as Caddy does (not /admin-help).
    match = re.search(r'"\^/admin\(/\|\$\)":\s*\{([^}]*)\}', VITE)
    assert match, "no /admin proxy entry"
    assert 'target: "http://backend:8000"' in match.group(1)
    assert "changeOrigin: false" in match.group(1)
