"""Scouting API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

scouting_bp = Blueprint("scouting_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@scouting_bp.route("/scouting")
def scouting_page():
    return render_template("scouting.html")


# ====================================================================
# Scouting API
# ====================================================================


@scouting_bp.route("/api/scouting/reports", methods=["GET"])
def get_scouting_reports():
    user_id = _user_id()
    area = request.args.get("area")
    request.args.get("status")
    request.args.get("severity")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from scouting_log import get_reports as _get_reports

        reports = _get_reports(user_id, start_date=start_date, end_date=end_date, area=area)
        return jsonify(reports)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting reports: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports", methods=["POST"])
def create_scouting_report():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from scouting_log import create_report as _create_report

        report = _create_report(user_id, data)
        return jsonify(report), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating scouting report: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports/<int:report_id>", methods=["GET"])
def get_scouting_report_by_id(report_id):
    user_id = _user_id()
    try:
        from scouting_log import get_report_by_id as _get_report

        report = _get_report(report_id, user_id)
        return jsonify(report)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting report {report_id}: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports/<int:report_id>", methods=["PUT"])
def update_scouting_report(report_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from scouting_log import update_report as _update_report

        report = _update_report(report_id, user_id, data)
        return jsonify(report)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating scouting report {report_id}: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports/<int:report_id>", methods=["DELETE"])
def delete_scouting_report(report_id):
    user_id = _user_id()
    try:
        from scouting_log import delete_report as _delete_report

        result = _delete_report(report_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting scouting report {report_id}: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports/<int:report_id>/status", methods=["PUT"])
def update_scouting_report_status(report_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    status = data.get("status", "")
    try:
        from scouting_log import update_report_status as _update_status

        result = _update_status(report_id, user_id, status)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating scouting report status {report_id}: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/open-issues", methods=["GET"])
def get_scouting_open_issues():
    user_id = _user_id()
    try:
        from scouting_log import get_open_issues as _get_open

        issues = _get_open(user_id)
        return jsonify(issues)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting open scouting issues: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports/<int:report_id>/photos", methods=["POST"])
def upload_scouting_photo(report_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    photo_data = data.get("photo_data", "")
    photo_type = data.get("photo_type", "initial")
    caption = data.get("caption", "")
    try:
        from scouting_log import add_photo as _add_photo

        result = _add_photo(report_id, user_id, photo_data, photo_type=photo_type, caption=caption)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error uploading scouting photo: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/reports/<int:report_id>/photos", methods=["GET"])
def get_scouting_photos(report_id):
    try:
        from scouting_log import get_photos as _get_photos

        photos = _get_photos(report_id)
        return jsonify(photos)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting photos: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/templates", methods=["GET"])
def get_scouting_templates():
    user_id = _user_id()
    try:
        from scouting_log import get_scouting_templates as _get_templates

        templates = _get_templates(user_id)
        return jsonify(templates)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting templates: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/templates", methods=["POST"])
def save_scouting_template():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from scouting_log import save_scouting_template as _save_template

        template = _save_template(user_id, data)
        return jsonify(template), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error saving scouting template: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/templates/<int:template_id>", methods=["GET"])
def get_scouting_template(template_id):
    user_id = _user_id()
    try:
        from scouting_log import get_scouting_template_by_id as _get_tmpl

        template = _get_tmpl(template_id, user_id)
        return jsonify(template)
    except Exception as e:
        logger.error(f"Error getting scouting template {template_id}: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/summary", methods=["GET"])
def get_scouting_summary():
    user_id = _user_id()
    days = request.args.get("days", 30, type=int)
    try:
        from scouting_log import get_issue_summary as _get_summary

        summary = _get_summary(user_id, days=days)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting summary: {e}")
        return jsonify({"error": str(e)}), 500


@scouting_bp.route("/api/scouting/export", methods=["GET"])
def export_scouting():
    """Export scouting reports as CSV or PDF."""
    user_id = _user_id()
    fmt = request.args.get("format", "csv").lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from scouting_log import get_reports as _get_reports

        reports = _get_reports(user_id, start_date=start_date, end_date=end_date)
        columns = [
            ("date", "Date"),
            ("area", "Area"),
            ("issue_type", "Issue Type"),
            ("severity", "Severity"),
            ("description", "Description"),
            ("status", "Status"),
        ]
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        if fmt == "pdf":
            from export_service import export_pdf

            return export_pdf(reports, "Scouting Reports", columns, f"scouting_{date_str}.pdf")
        from export_service import export_csv

        return export_csv(reports, columns, f"scouting_{date_str}.csv")
    except Exception as e:
        logger.error(f"Error exporting scouting reports: {e}")
        return jsonify({"error": str(e)}), 500
