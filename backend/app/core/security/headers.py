"""Secure HTTP response headers.

Applied via ``after_request`` so they cover every response — including JSON
APIs and error pages.

Notes:
* CSP is intentionally restrictive for the API. The Next.js frontend will set
  its own CSP via ``next.config.js``; we don't need a permissive script-src here.
* HSTS is enabled only when ``DEBUG=False`` to avoid pinning developer browsers.
"""

from __future__ import annotations

from flask import Flask, Response


_DEFAULT_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    # API never returns HTML, so a tight CSP is fine.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def register_security_headers(app: Flask) -> None:
    """Attach the ``after_request`` hook that stamps every response."""

    @app.after_request
    def _apply(response: Response) -> Response:
        for k, v in _DEFAULT_HEADERS.items():
            response.headers.setdefault(k, v)
        if not app.debug and not app.testing:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response
