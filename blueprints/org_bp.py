"""Organization management blueprint."""

import logging
import re

from flask import Blueprint, jsonify, request, session

from auth import login_required
from blueprints.org_context import add_org_member, create_org, get_org_member_role, get_user_orgs

logger = logging.getLogger(__name__)

org_bp = Blueprint("org", __name__)


@org_bp.route("/api/orgs", methods=["GET"])
@login_required
def list_orgs():
    """List organizations the current user belongs to."""
    orgs = get_user_orgs(session["user_id"])
    return jsonify(orgs)


@org_bp.route("/api/orgs", methods=["POST"])
@login_required
def create_organization():
    """Create a new organization. Creator becomes owner."""
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Organization name is required"}), 400

    # Generate slug from name
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        return jsonify({"error": "Invalid organization name"}), 400

    try:
        org_id = create_org(
            name=name,
            slug=slug,
            user_id=session["user_id"],
            course_name=data.get("course_name"),
            city=data.get("city"),
            state=data.get("state"),
        )
        # Auto-switch to the new org
        session["org_id"] = org_id
        return jsonify({"id": org_id, "slug": slug, "name": name})
    except Exception as e:
        logger.error(f"Failed to create org: {e}")
        return jsonify({"error": "Organization name already taken"}), 409


@org_bp.route("/api/orgs/<int:org_id>/members", methods=["GET"])
@login_required
def list_org_members(org_id):
    """List members of an organization."""
    role = get_org_member_role(org_id, session["user_id"])
    if not role:
        return jsonify({"error": "Not a member of this organization"}), 403

    from db import get_db

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.name, u.email, om.role, om.joined_at
            FROM org_members om
            JOIN users u ON u.id = om.user_id
            WHERE om.org_id = ?
            ORDER BY om.role, u.name
        """,
            (org_id,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@org_bp.route("/api/orgs/<int:org_id>/members", methods=["POST"])
@login_required
def invite_member(org_id):
    """Add a member to an organization. Requires admin or owner role."""
    role = get_org_member_role(org_id, session["user_id"])
    if role not in ("owner", "admin"):
        return jsonify({"error": "Only admins and owners can add members"}), 403

    data = request.json or {}
    user_email = data.get("email", "").strip()
    member_role = data.get("role", "member")

    if not user_email:
        return jsonify({"error": "Email is required"}), 400
    if member_role not in ("owner", "admin", "member", "viewer"):
        return jsonify({"error": "Invalid role"}), 400

    # Find user by email
    from db import get_db

    with get_db() as conn:
        user = conn.execute("SELECT id, name FROM users WHERE email = ?", (user_email,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    add_org_member(org_id, user["id"], member_role)
    return jsonify({"success": True, "user_id": user["id"], "role": member_role})


@org_bp.route("/api/orgs/<int:org_id>/switch", methods=["POST"])
@login_required
def switch_org(org_id):
    """Switch the active organization for the current session."""
    role = get_org_member_role(org_id, session["user_id"])
    if not role:
        return jsonify({"error": "Not a member of this organization"}), 403

    session["org_id"] = org_id
    return jsonify({"success": True, "org_id": org_id, "role": role})
