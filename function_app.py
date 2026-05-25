"""Azure Functions entrypoint for Greenside AI."""

from __future__ import annotations

from app import app as flask_app

try:  # pragma: no cover - deployment-only dependency
    import azure.functions as func
except ImportError:  # pragma: no cover - local/test environments
    func = None


if func is not None:  # pragma: no branch
    app = func.WsgiFunctionApp(app=flask_app.wsgi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
