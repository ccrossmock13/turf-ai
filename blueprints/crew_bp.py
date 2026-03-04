"""Crew Management API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _check_error, _user_id

logger = logging.getLogger(__name__)

crew_bp = Blueprint("crew_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@crew_bp.route("/crew")
def crew_page():
    return render_template("crew.html")


# ====================================================================
# Crew API
# ====================================================================


@crew_bp.route("/api/crew/members", methods=["GET"])
def get_crew_members():
    user_id = _user_id()
    role = request.args.get("role")
    active_only = request.args.get("active_only", "true").lower() == "true"
    try:
        from crew_management import get_crew_members as _get_members

        members = _get_members(user_id, role=role, active_only=active_only)
        return jsonify(members)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting crew members: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/members", methods=["POST"])
def create_crew_member():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import add_crew_member as _add_member

        member = _add_member(user_id, data)
        # add_crew_member returns {'error': ...} on failure instead of raising
        if isinstance(member, dict) and "error" in member:
            return jsonify(member), 400
        return jsonify(member), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating crew member: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/members/<int:member_id>", methods=["GET"])
def get_crew_member_by_id(member_id):
    user_id = _user_id()
    try:
        from crew_management import get_crew_member_by_id as _get_member

        member = _get_member(member_id, user_id)
        return jsonify(member)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting crew member {member_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/members/<int:member_id>", methods=["PUT"])
def update_crew_member(member_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import update_crew_member as _update_member

        member = _check_error(_update_member(member_id, user_id, data))
        return jsonify(member)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating crew member {member_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/members/<int:member_id>", methods=["DELETE"])
def delete_crew_member(member_id):
    user_id = _user_id()
    try:
        from crew_management import delete_crew_member_permanent as _delete_member

        result = _check_error(_delete_member(member_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting crew member {member_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/work-orders", methods=["GET"])
def get_work_orders():
    user_id = _user_id()
    status = request.args.get("status")
    area = request.args.get("area")
    assigned_to = request.args.get("assigned_to", type=int)
    try:
        from crew_management import get_work_orders as _get_wos

        orders = _get_wos(user_id, status=status, area=area, assigned_to=assigned_to)
        return jsonify(orders)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting work orders: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/work-orders", methods=["POST"])
def create_work_order():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import create_work_order as _create_wo

        order = _check_error(_create_wo(user_id, data))
        return jsonify(order), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating work order: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/work-orders/<int:order_id>", methods=["GET"])
def get_work_order_by_id(order_id):
    user_id = _user_id()
    try:
        from crew_management import get_work_order_by_id as _get_wo

        order = _get_wo(order_id, user_id)
        return jsonify(order)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting work order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/work-orders/<int:order_id>", methods=["PUT"])
def update_work_order(order_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import update_work_order as _update_wo

        order = _check_error(_update_wo(order_id, user_id, data))
        return jsonify(order)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating work order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/work-orders/<int:order_id>/assign", methods=["POST"])
def assign_work_order(order_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    crew_member_id = data.get("crew_member_id")
    try:
        from crew_management import assign_work_order as _assign_wo

        result = _check_error(_assign_wo(order_id, user_id, crew_member_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error assigning work order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/work-orders/<int:order_id>/complete", methods=["POST"])
def complete_work_order(order_id):
    user_id = _user_id()
    data = request.get_json(silent=True) or {}
    actual_hours = data.get("actual_hours")
    try:
        from crew_management import complete_work_order as _complete_wo

        result = _check_error(_complete_wo(order_id, user_id, actual_hours=actual_hours))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error completing work order {order_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/time-entries", methods=["GET"])
def get_time_entries():
    user_id = _user_id()
    member_id = request.args.get("member_id", type=int)
    start_date = request.args.get("start_date")
    request.args.get("end_date")
    try:
        from crew_management import get_time_entries as _get_te

        entries = _get_te(user_id, crew_member_id=member_id, start_date=start_date)
        return jsonify(entries)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting time entries: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/time-entries", methods=["POST"])
def create_time_entry():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import log_time as _log_time

        entry = _check_error(_log_time(user_id, data))
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating time entry: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/daily-assignments", methods=["GET"])
def get_daily_assignments():
    user_id = _user_id()
    date = request.args.get("date")
    try:
        from crew_management import get_daily_assignments as _get_da

        assignments = _get_da(user_id, date=date)
        return jsonify(assignments)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting daily assignments: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/daily-assignments", methods=["POST"])
def create_daily_assignment():
    user_id = _user_id()
    data = request.get_json(force=True)
    date = data.get("date")
    assignments = data.get("assignments", [])
    try:
        from crew_management import create_daily_assignments as _create_da

        result = _check_error(_create_da(user_id, date, assignments))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating daily assignment: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/daily-assignments/<int:assignment_id>/complete", methods=["POST"])
def complete_daily_assignment(assignment_id):
    user_id = _user_id()
    try:
        from crew_management import complete_assignment as _complete_assign

        result = _check_error(_complete_assign(assignment_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error completing daily assignment {assignment_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/daily-assignments/<int:assignment_id>", methods=["PUT"])
def update_daily_assignment(assignment_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import update_assignment as _update_assign

        result = _update_assign(assignment_id, user_id, data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating assignment {assignment_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/daily-assignments/<int:assignment_id>", methods=["DELETE"])
def delete_daily_assignment(assignment_id):
    user_id = _user_id()
    try:
        from crew_management import delete_assignment as _del_assign

        result = _del_assign(assignment_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting assignment {assignment_id}: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/labor-summary", methods=["GET"])
def get_labor_summary():
    user_id = _user_id()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from crew_management import get_labor_summary as _get_labor

        summary = _get_labor(user_id, start_date, end_date)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting labor summary: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/daily-sheet", methods=["GET"])
def get_daily_sheet():
    user_id = _user_id()
    date = request.args.get("date")
    try:
        from crew_management import generate_daily_sheet as _gen_sheet

        sheet = _gen_sheet(user_id, date=date)
        return jsonify(sheet)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting daily sheet: {e}")
        return jsonify({"error": str(e)}), 500


@crew_bp.route("/api/crew/export", methods=["GET"])
def export_crew():
    """Export crew members as CSV or PDF."""
    user_id = _user_id()
    fmt = request.args.get("format", "csv").lower()
    try:
        from crew_management import get_crew_members as _get_members

        members = _get_members(user_id)
        columns = [
            ("name", "Name"),
            ("role", "Role"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("hire_date", "Hire Date"),
            ("hourly_rate", "Hourly Rate"),
            ("status", "Status"),
        ]
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        if fmt == "pdf":
            from export_service import export_pdf

            return export_pdf(members, "Crew Roster", columns, f"crew_{date_str}.pdf")
        from export_service import export_csv

        return export_csv(members, columns, f"crew_{date_str}.csv")
    except Exception as e:
        logger.error(f"Error exporting crew: {e}")
        return jsonify({"error": str(e)}), 500
