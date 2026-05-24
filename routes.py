"""Legacy blueprint module.

The public page and resource routes now live in app.py so they share the same
auth/context helpers and homepage boot payload. We keep this blueprint module
as a stable import target for app setup while avoiding duplicate route
registration.
"""

from flask import Blueprint


turf_bp = Blueprint("turf_bp", __name__)
