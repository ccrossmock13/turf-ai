"""AWS Lambda entrypoint for Greenside AI.

Requires an adapter such as `awsgi` in the deployment package.
"""

from __future__ import annotations

from app import app


def lambda_handler(event, context):
    try:
        import awsgi
    except ImportError as exc:  # pragma: no cover - deployment-only dependency
        raise RuntimeError(
            "AWS Lambda adapter not installed. Add `awsgi` to the deployment package."
        ) from exc
    return awsgi.response(app, event, context)
