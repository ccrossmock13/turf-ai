"""Reports API blueprint."""

from flask import Blueprint, jsonify, request, render_template
import logging

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

reporting_bp = Blueprint('reporting_bp', __name__)


# ====================================================================
# Page Route
# ====================================================================

@reporting_bp.route('/reports')
def reports_page():
    return render_template('reports.html')


# ====================================================================
# Reports API
# ====================================================================

@reporting_bp.route('/api/reports/generate', methods=['POST'])
def generate_report():
    user_id = _user_id()
    data = request.get_json(force=True)
    report_type = data.get('report_type', 'monthly')
    year = data.get('year')
    month = data.get('month')
    try:
        if report_type == 'monthly':
            from reporting import generate_monthly_report as _gen
            report = _gen(user_id, year, month)
        elif report_type == 'green_committee':
            from reporting import generate_green_committee_report as _gen
            report = _gen(user_id, year, month)
        elif report_type == 'annual':
            from reporting import generate_annual_report as _gen
            report = _gen(user_id, year)
        elif report_type == 'pesticide_compliance':
            from reporting import generate_pesticide_compliance_report as _gen
            report = _gen(user_id, year)
        else:
            from reporting import generate_monthly_report as _gen
            report = _gen(user_id, year, month)
        return jsonify(report), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/generate', methods=['GET'])
def preview_report():
    user_id = _user_id()
    report_type = request.args.get('type', 'monthly')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    try:
        if report_type == 'monthly':
            from reporting import generate_monthly_report as _gen
            report = _gen(user_id, year, month)
        elif report_type == 'green_committee':
            from reporting import generate_green_committee_report as _gen
            report = _gen(user_id, year, month)
        elif report_type == 'annual':
            from reporting import generate_annual_report as _gen
            report = _gen(user_id, year)
        elif report_type == 'pesticide_compliance':
            from reporting import generate_pesticide_compliance_report as _gen
            report = _gen(user_id, year)
        else:
            from reporting import generate_monthly_report as _gen
            report = _gen(user_id, year, month)
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error previewing report: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/save', methods=['POST'])
def save_report():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from reporting import save_report as _save
        result = _save(user_id, data)
        report = {'id': result} if isinstance(result, int) else result
        return jsonify(report), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error saving report: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/list', methods=['GET'])
def list_reports():
    user_id = _user_id()
    report_type = request.args.get('type')
    try:
        from reporting import get_reports as _get_reports
        reports = _get_reports(user_id, report_type=report_type)
        return jsonify(reports)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/list/<int:report_id>', methods=['GET'])
@reporting_bp.route('/api/reports/<int:report_id>', methods=['GET'])
def get_report(report_id):
    user_id = _user_id()
    try:
        from reporting import get_report_by_id as _get_report
        report = _get_report(report_id, user_id)
        return jsonify(report)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting report {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/list/<int:report_id>', methods=['DELETE'])
@reporting_bp.route('/api/reports/<int:report_id>', methods=['DELETE'])
def delete_report(report_id):
    user_id = _user_id()
    try:
        from reporting import delete_report as _del_report
        result = _del_report(report_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/export/<int:report_id>', methods=['GET'])
def export_report(report_id):
    user_id = _user_id()
    try:
        from reporting import export_report_html as _export
        result = _export(report_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error exporting report {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/export', methods=['GET'])
def export_report_by_params():
    user_id = _user_id()
    report_type = request.args.get('type', 'monthly')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    fmt = request.args.get('format', 'html')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    try:
        if report_type in ('monthly', 'green_committee'):
            from reporting import generate_monthly_report as _gen
            report = _gen(user_id, year, month)
        else:
            from reporting import generate_annual_report as _gen
            report = _gen(user_id, year)
        from reporting import export_report_html as _export
        html = _export(report.get('id', 0) if isinstance(report, dict) else 0, user_id)
        return jsonify(html)
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/compliance', methods=['GET'])
def get_compliance_reports():
    user_id = _user_id()
    record_type = request.args.get('record_type')
    year = request.args.get('year', type=int)
    try:
        from reporting import get_compliance_records as _get_compliance
        reports = _get_compliance(user_id, record_type=record_type, year=year)
        return jsonify(reports)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting compliance reports: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/compliance', methods=['POST'])
def create_compliance_report():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from reporting import log_compliance_record as _log_compliance
        result = _log_compliance(user_id, data)
        report = {'id': result} if isinstance(result, int) else result
        return jsonify(report), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating compliance report: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/compliance/gap-check', methods=['GET'])
@reporting_bp.route('/api/reports/compliance/gaps', methods=['GET'])
def get_compliance_gaps():
    user_id = _user_id()
    year = request.args.get('year', type=int)
    try:
        from reporting import check_compliance_gaps as _check_gaps
        gaps = _check_gaps(user_id, year)
        return jsonify(gaps)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting compliance gaps: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/compliance/<int:record_id>', methods=['DELETE'])
def delete_compliance_record(record_id):
    user_id = _user_id()
    try:
        from reporting import delete_compliance_record as _del_compliance
        result = _del_compliance(record_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting compliance record {record_id}: {e}")
        return jsonify({'error': str(e)}), 500


@reporting_bp.route('/api/reports/compliance/export', methods=['GET'])
def export_compliance_records():
    user_id = _user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    fmt = request.args.get('format', 'csv')
    try:
        from reporting import export_compliance_records as _export_compliance
        result = _export_compliance(user_id, start_date=start_date, end_date=end_date, fmt=fmt)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error exporting compliance records: {e}")
        return jsonify({'error': str(e)}), 500
