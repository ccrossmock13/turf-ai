"""Shared helpers for all blueprints."""

from flask import session


def _user_id():
    """Return the current user id, defaulting to 1 for demo mode."""
    return session.get("user_id", 1)


def _check_error(result):
    """Some modules return {'error': ...} instead of raising. Raise ValueError if so."""
    if isinstance(result, dict) and "error" in result:
        raise ValueError(result["error"])
    return result
