"""Notifications API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@notifications_bp.route("/notifications-page")
def notifications_page():
    return render_template("dashboard.html")


# ====================================================================
# Notifications API
# ====================================================================


@notifications_bp.route("/api/notifications", methods=["GET"])
def get_notifications():
    user_id = _user_id()
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    try:
        from notifications import get_notifications as _get_notifs

        notifs = _get_notifs(user_id, unread_only=unread_only, limit=limit)
        return jsonify(notifs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id):
    user_id = _user_id()
    try:
        from notifications import mark_read as _mark_read

        result = _mark_read(notification_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/read-all", methods=["POST"])
def mark_all_notifications_read():
    user_id = _user_id()
    try:
        from notifications import mark_all_read as _mark_all

        result = _mark_all(user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/<int:notification_id>/dismiss", methods=["POST"])
def dismiss_notification(notification_id):
    user_id = _user_id()
    try:
        from notifications import dismiss_notification as _dismiss

        result = _dismiss(notification_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error dismissing notification {notification_id}: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/unread-count", methods=["GET"])
def get_unread_count():
    user_id = _user_id()
    try:
        from notifications import get_unread_count as _unread

        count = _unread(user_id)
        return jsonify(count)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/preferences", methods=["GET"])
def get_notification_preferences():
    user_id = _user_id()
    try:
        from notifications import get_preferences as _get_prefs

        prefs = _get_prefs(user_id)
        return jsonify(prefs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting notification preferences: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/preferences", methods=["PUT"])
def update_notification_preferences():
    user_id = _user_id()
    data = request.get_json(force=True)
    notification_type = data.get("notification_type")
    enabled = data.get("enabled")
    email_enabled = data.get("email_enabled")
    push_enabled = data.get("push_enabled")
    try:
        from notifications import update_preference as _update_pref

        prefs = _update_pref(
            user_id, notification_type, enabled=enabled, email_enabled=email_enabled, push_enabled=push_enabled
        )
        return jsonify(prefs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/rules", methods=["GET"])
def get_notification_rules():
    user_id = _user_id()
    try:
        from notifications import get_rules as _get_rules

        rules = _get_rules(user_id)
        return jsonify(rules)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting notification rules: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/rules", methods=["POST"])
def create_notification_rule():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from notifications import create_rule as _create_rule

        rule = _create_rule(user_id, data)
        return jsonify(rule), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating notification rule: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/rules/<int:rule_id>", methods=["PUT"])
def update_notification_rule(rule_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from notifications import update_rule as _update_rule

        rule = _update_rule(rule_id, user_id, data)
        return jsonify(rule)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating notification rule {rule_id}: {e}")
        return jsonify({"error": str(e)}), 500


@notifications_bp.route("/api/notifications/rules/<int:rule_id>", methods=["DELETE"])
def delete_notification_rule(rule_id):
    user_id = _user_id()
    try:
        from notifications import delete_rule as _delete_rule

        result = _delete_rule(rule_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting notification rule {rule_id}: {e}")
        return jsonify({"error": str(e)}), 500
