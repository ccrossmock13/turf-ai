"""
Feature Routes Blueprint for Greenside AI Turfgrass Management App.

This module registers all API routes for the feature modules:
- Calendar/Scheduler
- Budget Tracker
- Scouting Log
- Crew Management
- Equipment Manager
- Irrigation Manager
- Soil Testing
- Community
- Cultivar Tool
- Notifications
- Reporting
- Unit Converter / Calculator
- Course Map
"""

from flask import Blueprint, render_template, jsonify, request, session
import json
import logging

logger = logging.getLogger(__name__)

features_bp = Blueprint('features_bp', __name__)


# ---------------------------------------------------------------------------
# Database table initialization
# ---------------------------------------------------------------------------

def init_all_feature_tables():
    """Initialize database tables for all feature modules."""
    modules = [
        ('calendar_scheduler', 'init_calendar_tables'),
        ('budget_tracker', 'init_budget_tables'),
        ('scouting_log', 'init_scouting_tables'),
        ('crew_management', 'init_crew_tables'),
        ('equipment_manager', 'init_equipment_tables'),
        ('irrigation_manager', 'init_irrigation_tables'),
        ('soil_testing', 'init_soil_tables'),
        ('community', 'init_community_tables'),
        ('cultivar_tool', 'init_cultivar_tables'),
        ('notifications', 'init_notification_tables'),
        ('reporting', 'init_reporting_tables'),
        ('course_map', 'init_map_tables'),
    ]
    for module_name, func_name in modules:
        try:
            mod = __import__(module_name)
            init_fn = getattr(mod, func_name)
            init_fn()
            logger.info(f"Initialized tables for {module_name}")
        except Exception as e:
            logger.warning(f"Could not initialize tables for {module_name}: {e}")

    # Seed cultivar data if tables are empty
    try:
        from cultivar_tool import seed_cultivar_data
        seed_cultivar_data()
    except Exception as e:
        logger.warning(f"Could not seed cultivar data: {e}")


# ====================================================================
# Helper
# ====================================================================

def _user_id():
    """Return the current user id, defaulting to 1 for demo mode."""
    return session.get('user_id', 1)


def _check_error(result):
    """Some modules return {'error': ...} instead of raising. Raise ValueError if so."""
    if isinstance(result, dict) and 'error' in result:
        raise ValueError(result['error'])
    return result


# Mapping: template abbreviated names → backend full column names
_SOIL_FIELD_MAP = {
    'date': 'test_date',
    'lab': 'lab_name',
    'om_pct': 'organic_matter',
    'p_ppm': 'phosphorus_ppm',
    'k_ppm': 'potassium_ppm',
    'ca_ppm': 'calcium_ppm',
    'mg_ppm': 'magnesium_ppm',
    's_ppm': 'sulfur_ppm',
    'fe_ppm': 'iron_ppm',
    'mn_ppm': 'manganese_ppm',
    'zn_ppm': 'zinc_ppm',
    'cu_ppm': 'copper_ppm',
    'b_ppm': 'boron_ppm',
    'na_ppm': 'sodium_ppm',
    'no3_ppm': 'nitrate_ppm',
    'ca_sat': 'base_saturation_ca',
    'mg_sat': 'base_saturation_mg',
    'k_sat': 'base_saturation_k',
    'na_sat': 'base_saturation_na',
    'h_sat': 'base_saturation_h',
}
_SOIL_FIELD_MAP_REV = {v: k for k, v in _SOIL_FIELD_MAP.items()}


_WATER_FIELD_MAP = {
    'date': 'test_date',
    'tds': 'tds_ppm',
    'hardness': 'hardness_ppm',
    'alkalinity': 'bicarbonate_ppm',
    'na_ppm': 'sodium_ppm',
    'ca_ppm': 'calcium_ppm',
    'mg_ppm': 'magnesium_ppm',
    'cl_ppm': 'chloride_ppm',
    'hco3_ppm': 'bicarbonate_ppm',
    'fe_ppm': 'iron_ppm',
}
_WATER_FIELD_MAP_REV = {v: k for k, v in _WATER_FIELD_MAP.items()}


def _soil_inbound(data):
    """Map abbreviated template field names to full backend column names."""
    mapped = dict(data)
    for short, full in _SOIL_FIELD_MAP.items():
        if short in mapped and full not in mapped:
            mapped[full] = mapped.pop(short)
    return mapped


def _water_inbound(data):
    """Map abbreviated water test field names to full backend column names."""
    mapped = dict(data)
    for short, full in _WATER_FIELD_MAP.items():
        if short in mapped and full not in mapped:
            mapped[full] = mapped.pop(short)
    return mapped


def _soil_outbound(record):
    """Add abbreviated aliases to a soil test record for template compatibility."""
    if not isinstance(record, dict):
        return record
    out = dict(record)
    for full, short in _SOIL_FIELD_MAP_REV.items():
        if full in out and short not in out:
            out[short] = out[full]
    return out


# ====================================================================
# Page Routes
# ====================================================================

@features_bp.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')


@features_bp.route('/calendar')
def calendar_page():
    return render_template('calendar.html')


@features_bp.route('/budget')
def budget_page():
    return render_template('budget.html')


@features_bp.route('/scouting')
def scouting_page():
    return render_template('scouting.html')


@features_bp.route('/crew')
def crew_page():
    return render_template('crew.html')


@features_bp.route('/equipment')
def equipment_page():
    return render_template('equipment.html')


@features_bp.route('/irrigation')
def irrigation_page():
    return render_template('irrigation.html')


@features_bp.route('/soil')
def soil_page():
    return render_template('soil.html')


@features_bp.route('/community')
def community_page():
    return render_template('community.html')


@features_bp.route('/cultivars')
def cultivars_page():
    return render_template('cultivars.html')


@features_bp.route('/notifications-page')
def notifications_page():
    return render_template('dashboard.html')


@features_bp.route('/reports')
def reports_page():
    return render_template('reports.html')


@features_bp.route('/calculator')
def calculator_page():
    return render_template('calculator.html')


@features_bp.route('/course-map')
def course_map_page():
    return render_template('course-map.html')


# ====================================================================
# Calendar API
# Signatures:
#   create_event(user_id, data)
#   update_event(event_id, user_id, data)
#   delete_event(event_id, user_id)
#   get_events(user_id, start_date, end_date, area=None, event_type=None)
#   get_event_by_id(event_id, user_id)
#   complete_event(event_id, user_id)
#   get_upcoming_events(user_id, days=7)
#   get_overdue_events(user_id)
#   get_calendar_templates(user_id)
#   save_calendar_template(user_id, data)
#   apply_template(user_id, template_id, start_date)
# ====================================================================

@features_bp.route('/api/calendar/events', methods=['GET'])
def get_calendar_events():
    user_id = _user_id()
    start = request.args.get('start')
    end = request.args.get('end')
    area = request.args.get('area')
    event_type = request.args.get('event_type')
    try:
        from calendar_scheduler import get_events as _get_events
        events = _get_events(user_id, start, end, area, event_type)
        return jsonify(events)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting calendar events: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/events', methods=['POST'])
def create_calendar_event():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from calendar_scheduler import create_event as _create_event
        result = _create_event(user_id, data)
        # create_event returns bare int ID - fetch full record
        from calendar_scheduler import get_event_by_id as _get_event
        event = _get_event(result, user_id) if isinstance(result, int) else result
        return jsonify(event), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/events/<int:event_id>', methods=['GET'])
def get_calendar_event_by_id(event_id):
    user_id = _user_id()
    try:
        from calendar_scheduler import get_event_by_id as _get_event
        event = _get_event(event_id, user_id)
        return jsonify(event)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting calendar event {event_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/events/<int:event_id>', methods=['PUT'])
def update_calendar_event(event_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from calendar_scheduler import update_event as _update_event
        event = _update_event(event_id, user_id, data)
        return jsonify(event)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating calendar event {event_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
def delete_calendar_event(event_id):
    user_id = _user_id()
    try:
        from calendar_scheduler import delete_event as _delete_event
        result = _delete_event(event_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting calendar event {event_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/events/<int:event_id>/complete', methods=['POST'])
def complete_calendar_event(event_id):
    user_id = _user_id()
    try:
        from calendar_scheduler import complete_event as _complete_event
        result = _complete_event(event_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error completing calendar event {event_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/upcoming', methods=['GET'])
def get_upcoming_events():
    user_id = _user_id()
    days = request.args.get('days', 7, type=int)
    try:
        from calendar_scheduler import get_upcoming_events as _get_upcoming
        events = _get_upcoming(user_id, days)
        return jsonify(events)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting upcoming events: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/overdue', methods=['GET'])
def get_overdue_events():
    user_id = _user_id()
    try:
        from calendar_scheduler import get_overdue_events as _get_overdue
        events = _get_overdue(user_id)
        return jsonify(events)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting overdue events: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/templates', methods=['GET'])
def get_calendar_templates():
    user_id = _user_id()
    try:
        from calendar_scheduler import get_calendar_templates as _get_templates
        templates = _get_templates(user_id)
        return jsonify(templates)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting calendar templates: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/templates', methods=['POST'])
def save_calendar_template():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from calendar_scheduler import save_calendar_template as _save_template
        result = _save_template(user_id, data)
        template = {'id': result} if isinstance(result, int) else result
        return jsonify(template), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error saving calendar template: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calendar/templates/apply', methods=['POST'])
def apply_calendar_template():
    user_id = _user_id()
    data = request.get_json(force=True)
    template_id = data.get('template_id')
    start_date = data.get('start_date')
    try:
        from calendar_scheduler import apply_template as _apply_template
        result = _apply_template(user_id, template_id, start_date)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error applying calendar template: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Budget API
# Signatures:
#   create_budget(user_id, data)
#   update_budget(budget_id, user_id, data)
#   delete_budget(budget_id, user_id)
#   get_budgets(user_id, fiscal_year=None)
#   get_budget_summary(user_id, fiscal_year)
#   create_purchase_order(user_id, data)
#   update_purchase_order(po_id, user_id, data)
#   update_po_status(po_id, user_id, status)
#   delete_purchase_order(user_id, po_id)
#   get_purchase_orders(user_id, status=None, vendor=None)
#   create_expense(user_id, data)
#   update_expense(user_id, expense_id, data)
#   delete_expense(user_id, expense_id)
#   get_expenses(user_id, start_date=None, end_date=None, category=None)
#   get_cost_per_acre(user_id, fiscal_year, area=None)
#   get_vendor_summary(user_id, fiscal_year)
# ====================================================================

@features_bp.route('/api/budget/budgets', methods=['GET'])
def get_budgets():
    user_id = _user_id()
    year = request.args.get('year', type=int)
    try:
        from budget_tracker import get_budgets as _get_budgets
        budgets = _get_budgets(user_id, fiscal_year=year)
        return jsonify(budgets)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting budgets: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/budgets', methods=['POST'])
def create_budget():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import create_budget as _create_budget
        budget_id = _create_budget(user_id, data)
        # create_budget returns just an int ID - fetch the full record
        from budget_tracker import get_budget_by_id as _get_budget
        budget = _get_budget(budget_id, user_id)
        return jsonify(budget), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating budget: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/budgets/<int:budget_id>', methods=['PUT'])
def update_budget(budget_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_budget as _update_budget
        _update_budget(budget_id, user_id, data)
        # update_budget returns True/False - fetch the updated record
        from budget_tracker import get_budget_by_id as _get_budget
        budget = _get_budget(budget_id, user_id)
        return jsonify(budget)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating budget {budget_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/budgets/<int:budget_id>', methods=['DELETE'])
def delete_budget(budget_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_budget as _delete_budget
        result = _delete_budget(budget_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting budget {budget_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/summary', methods=['GET'])
def get_budget_summary():
    user_id = _user_id()
    year = request.args.get('year', type=int)
    try:
        from budget_tracker import get_budget_summary as _get_summary
        summary = _get_summary(user_id, year)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting budget summary: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/purchase-orders', methods=['GET'])
def get_purchase_orders():
    user_id = _user_id()
    status = request.args.get('status')
    vendor = request.args.get('vendor')
    try:
        from budget_tracker import get_purchase_orders as _get_pos
        pos = _get_pos(user_id, status=status, vendor=vendor)
        return jsonify(pos)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting purchase orders: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/purchase-orders', methods=['POST'])
def create_purchase_order():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import create_purchase_order as _create_po
        po = _create_po(user_id, data)
        return jsonify(po), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating purchase order: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/purchase-orders/<int:po_id>', methods=['PUT'])
def update_purchase_order(po_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_purchase_order as _update_po
        po = _update_po(po_id, user_id, data)
        return jsonify(po)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating purchase order {po_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/purchase-orders/<int:po_id>', methods=['DELETE'])
def delete_purchase_order(po_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_purchase_order as _delete_po
        result = _delete_po(user_id, po_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting purchase order {po_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/purchase-orders/<int:po_id>/status', methods=['POST', 'PUT'])
def update_po_status(po_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_po_status as _update_po_status
        status = data.get('status', '')
        result = _update_po_status(po_id, user_id, status)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating PO status {po_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/expenses', methods=['GET'])
def get_expenses():
    user_id = _user_id()
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from budget_tracker import get_expenses as _get_expenses
        expenses = _get_expenses(user_id, start_date=start_date, end_date=end_date, category=category)
        return jsonify(expenses)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/expenses', methods=['POST'])
def create_expense():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import log_expense as _create_expense
        expense = _create_expense(user_id, data)
        return jsonify(expense), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import update_expense as _update_expense
        expense = _update_expense(user_id, expense_id, data)
        return jsonify(expense)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating expense {expense_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_expense as _delete_expense
        result = _delete_expense(user_id, expense_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting expense {expense_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/cost-per-acre', methods=['GET'])
def get_cost_per_acre():
    user_id = _user_id()
    year = request.args.get('year', type=int)
    area = request.args.get('area')
    try:
        from budget_tracker import get_cost_per_acre as _get_cpa
        result = _get_cpa(user_id, year, area=area)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting cost per acre: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/vendor-summary', methods=['GET'])
def get_vendor_summary():
    user_id = _user_id()
    year = request.args.get('year', type=int)
    try:
        from budget_tracker import get_vendor_summary as _get_vendor
        result = _get_vendor(user_id, year)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting vendor summary: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Scouting API
# Signatures:
#   create_report(user_id, data)
#   update_report(report_id, user_id, data)
#   delete_report(report_id, user_id)
#   get_reports(user_id, start_date=None, end_date=None, area=None, ...)
#   get_report_by_id(report_id, user_id)
#   update_report_status(report_id, user_id, status)
#   get_open_issues(user_id)
#   add_photo(report_id, user_id, photo_data, photo_type='initial', caption='')
#   get_photos(report_id)
#   get_scouting_templates(user_id)
#   save_scouting_template(user_id, data)
#   get_issue_summary(user_id, days=30)
# ====================================================================

@features_bp.route('/api/scouting/reports', methods=['GET'])
def get_scouting_reports():
    user_id = _user_id()
    area = request.args.get('area')
    status = request.args.get('status')
    severity = request.args.get('severity')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from scouting_log import get_reports as _get_reports
        reports = _get_reports(user_id, start_date=start_date, end_date=end_date, area=area)
        return jsonify(reports)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting reports: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports', methods=['POST'])
def create_scouting_report():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from scouting_log import create_report as _create_report
        report = _create_report(user_id, data)
        return jsonify(report), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating scouting report: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports/<int:report_id>', methods=['GET'])
def get_scouting_report_by_id(report_id):
    user_id = _user_id()
    try:
        from scouting_log import get_report_by_id as _get_report
        report = _get_report(report_id, user_id)
        return jsonify(report)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting report {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports/<int:report_id>', methods=['PUT'])
def update_scouting_report(report_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from scouting_log import update_report as _update_report
        report = _update_report(report_id, user_id, data)
        return jsonify(report)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating scouting report {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports/<int:report_id>', methods=['DELETE'])
def delete_scouting_report(report_id):
    user_id = _user_id()
    try:
        from scouting_log import delete_report as _delete_report
        result = _delete_report(report_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting scouting report {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports/<int:report_id>/status', methods=['PUT'])
def update_scouting_report_status(report_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    status = data.get('status', '')
    try:
        from scouting_log import update_report_status as _update_status
        result = _update_status(report_id, user_id, status)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating scouting report status {report_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/open-issues', methods=['GET'])
def get_scouting_open_issues():
    user_id = _user_id()
    try:
        from scouting_log import get_open_issues as _get_open
        issues = _get_open(user_id)
        return jsonify(issues)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting open scouting issues: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports/<int:report_id>/photos', methods=['POST'])
def upload_scouting_photo(report_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    photo_data = data.get('photo_data', '')
    photo_type = data.get('photo_type', 'initial')
    caption = data.get('caption', '')
    try:
        from scouting_log import add_photo as _add_photo
        result = _add_photo(report_id, user_id, photo_data, photo_type=photo_type, caption=caption)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error uploading scouting photo: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/reports/<int:report_id>/photos', methods=['GET'])
def get_scouting_photos(report_id):
    try:
        from scouting_log import get_photos as _get_photos
        photos = _get_photos(report_id)
        return jsonify(photos)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting photos: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/templates', methods=['GET'])
def get_scouting_templates():
    user_id = _user_id()
    try:
        from scouting_log import get_scouting_templates as _get_templates
        templates = _get_templates(user_id)
        return jsonify(templates)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting templates: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/templates', methods=['POST'])
def save_scouting_template():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from scouting_log import save_scouting_template as _save_template
        template = _save_template(user_id, data)
        return jsonify(template), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error saving scouting template: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/scouting/summary', methods=['GET'])
def get_scouting_summary():
    user_id = _user_id()
    days = request.args.get('days', 30, type=int)
    try:
        from scouting_log import get_issue_summary as _get_summary
        summary = _get_summary(user_id, days=days)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting scouting summary: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Crew API
# Signatures:
#   add_crew_member(user_id, data)
#   update_crew_member(member_id, user_id, data)
#   deactivate_crew_member(member_id, user_id)
#   get_crew_members(user_id, role=None, active_only=True)
#   get_crew_member_by_id(member_id, user_id)
#   create_work_order(user_id, data)
#   update_work_order(wo_id, user_id, data)
#   assign_work_order(wo_id, user_id, crew_member_id)
#   complete_work_order(wo_id, user_id, actual_hours=None)
#   get_work_orders(user_id, status=None, area=None, assigned_to=None, ...)
#   get_work_order_by_id(wo_id, user_id)
#   log_time(user_id, data)
#   get_time_entries(user_id, crew_member_id=None, start_date=None, ...)
#   get_daily_assignments(user_id, date=None)
#   create_daily_assignments(user_id, date, assignments)
#   complete_assignment(assignment_id, user_id)
#   generate_daily_sheet(user_id, date=None)
#   get_labor_summary(user_id, start_date, end_date)
# ====================================================================

@features_bp.route('/api/crew/members', methods=['GET'])
def get_crew_members():
    user_id = _user_id()
    role = request.args.get('role')
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    try:
        from crew_management import get_crew_members as _get_members
        members = _get_members(user_id, role=role, active_only=active_only)
        return jsonify(members)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting crew members: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/members', methods=['POST'])
def create_crew_member():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import add_crew_member as _add_member
        member = _add_member(user_id, data)
        # add_crew_member returns {'error': ...} on failure instead of raising
        if isinstance(member, dict) and 'error' in member:
            return jsonify(member), 400
        return jsonify(member), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating crew member: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/members/<int:member_id>', methods=['GET'])
def get_crew_member_by_id(member_id):
    user_id = _user_id()
    try:
        from crew_management import get_crew_member_by_id as _get_member
        member = _get_member(member_id, user_id)
        return jsonify(member)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting crew member {member_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/members/<int:member_id>', methods=['PUT'])
def update_crew_member(member_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import update_crew_member as _update_member
        member = _check_error(_update_member(member_id, user_id, data))
        return jsonify(member)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating crew member {member_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/members/<int:member_id>', methods=['DELETE'])
def delete_crew_member(member_id):
    user_id = _user_id()
    try:
        from crew_management import delete_crew_member_permanent as _delete_member
        result = _check_error(_delete_member(member_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting crew member {member_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/work-orders', methods=['GET'])
def get_work_orders():
    user_id = _user_id()
    status = request.args.get('status')
    area = request.args.get('area')
    assigned_to = request.args.get('assigned_to', type=int)
    try:
        from crew_management import get_work_orders as _get_wos
        orders = _get_wos(user_id, status=status, area=area, assigned_to=assigned_to)
        return jsonify(orders)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting work orders: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/work-orders', methods=['POST'])
def create_work_order():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import create_work_order as _create_wo
        order = _check_error(_create_wo(user_id, data))
        return jsonify(order), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating work order: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/work-orders/<int:order_id>', methods=['GET'])
def get_work_order_by_id(order_id):
    user_id = _user_id()
    try:
        from crew_management import get_work_order_by_id as _get_wo
        order = _get_wo(order_id, user_id)
        return jsonify(order)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting work order {order_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/work-orders/<int:order_id>', methods=['PUT'])
def update_work_order(order_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import update_work_order as _update_wo
        order = _check_error(_update_wo(order_id, user_id, data))
        return jsonify(order)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating work order {order_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/work-orders/<int:order_id>/assign', methods=['POST'])
def assign_work_order(order_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    crew_member_id = data.get('crew_member_id')
    try:
        from crew_management import assign_work_order as _assign_wo
        result = _check_error(_assign_wo(order_id, user_id, crew_member_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error assigning work order {order_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/work-orders/<int:order_id>/complete', methods=['POST'])
def complete_work_order(order_id):
    user_id = _user_id()
    data = request.get_json(silent=True) or {}
    actual_hours = data.get('actual_hours')
    try:
        from crew_management import complete_work_order as _complete_wo
        result = _check_error(_complete_wo(order_id, user_id, actual_hours=actual_hours))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error completing work order {order_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/time-entries', methods=['GET'])
def get_time_entries():
    user_id = _user_id()
    member_id = request.args.get('member_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from crew_management import get_time_entries as _get_te
        entries = _get_te(user_id, crew_member_id=member_id, start_date=start_date)
        return jsonify(entries)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting time entries: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/time-entries', methods=['POST'])
def create_time_entry():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import log_time as _log_time
        entry = _check_error(_log_time(user_id, data))
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating time entry: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/daily-assignments', methods=['GET'])
def get_daily_assignments():
    user_id = _user_id()
    date = request.args.get('date')
    try:
        from crew_management import get_daily_assignments as _get_da
        assignments = _get_da(user_id, date=date)
        return jsonify(assignments)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting daily assignments: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/daily-assignments', methods=['POST'])
def create_daily_assignment():
    user_id = _user_id()
    data = request.get_json(force=True)
    date = data.get('date')
    assignments = data.get('assignments', [])
    try:
        from crew_management import create_daily_assignments as _create_da
        result = _check_error(_create_da(user_id, date, assignments))
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating daily assignment: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/daily-assignments/<int:assignment_id>/complete', methods=['POST'])
def complete_daily_assignment(assignment_id):
    user_id = _user_id()
    try:
        from crew_management import complete_assignment as _complete_assign
        result = _check_error(_complete_assign(assignment_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error completing daily assignment {assignment_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/labor-summary', methods=['GET'])
def get_labor_summary():
    user_id = _user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from crew_management import get_labor_summary as _get_labor
        summary = _get_labor(user_id, start_date, end_date)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting labor summary: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/daily-sheet', methods=['GET'])
def get_daily_sheet():
    user_id = _user_id()
    date = request.args.get('date')
    try:
        from crew_management import generate_daily_sheet as _gen_sheet
        sheet = _gen_sheet(user_id, date=date)
        return jsonify(sheet)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting daily sheet: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Equipment API
# Signatures:
#   add_equipment(user_id, data)
#   update_equipment(equip_id, user_id, data)
#   retire_equipment(equip_id, user_id)
#   get_equipment(user_id, equipment_type=None, status=None)
#   get_equipment_by_id(equip_id, user_id)
#   log_maintenance(user_id, data)
#   get_maintenance_history(equip_id, user_id)
#   get_upcoming_maintenance(user_id, days=30)
#   get_overdue_maintenance(user_id)
#   log_hours(user_id, data)
#   get_hours_log(equip_id, user_id, start_date=None, end_date=None)
#   log_calibration(user_id, data)
#   get_calibration_history(equip_id, user_id)
#   get_fleet_summary(user_id)
# ====================================================================

# -- Seed-data endpoints (manufacturers, models, service intervals) --

@features_bp.route('/api/equipment/seed/manufacturers', methods=['GET'])
def get_manufacturers():
    """Return the full list of known equipment manufacturers."""
    try:
        from equipment_seed_data import MANUFACTURERS
        return jsonify(MANUFACTURERS)
    except Exception as e:
        logger.error(f"Error getting manufacturers: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/seed/models', methods=['GET'])
def get_seed_models():
    """Return equipment models, optionally filtered by manufacturer and/or type."""
    try:
        from equipment_seed_data import EQUIPMENT_MODELS
        manufacturer = request.args.get('manufacturer')
        eq_type = request.args.get('type')
        models = EQUIPMENT_MODELS
        if manufacturer:
            models = [m for m in models if m['manufacturer'] == manufacturer]
        if eq_type:
            models = [m for m in models if m['equipment_type'] == eq_type]
        return jsonify(models)
    except Exception as e:
        logger.error(f"Error getting seed models: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/seed/service-intervals', methods=['GET'])
def get_service_intervals():
    """Return standard service intervals for an equipment type."""
    try:
        from equipment_seed_data import SERVICE_INTERVALS
        eq_type = request.args.get('type')
        if eq_type and eq_type in SERVICE_INTERVALS:
            return jsonify(SERVICE_INTERVALS[eq_type])
        return jsonify(SERVICE_INTERVALS)
    except Exception as e:
        logger.error(f"Error getting service intervals: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment', methods=['GET'])
def get_equipment():
    user_id = _user_id()
    equipment_type = request.args.get('type')
    status = request.args.get('status')
    try:
        from equipment_manager import get_equipment as _get_equip
        equipment = _get_equip(user_id, equipment_type=equipment_type, status=status)
        return jsonify(equipment)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting equipment: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment', methods=['POST'])
def create_equipment():
    user_id = _user_id()
    data = request.get_json(force=True)
    # Template sends 'type' but backend expects 'equipment_type'
    if 'type' in data and 'equipment_type' not in data:
        data['equipment_type'] = data['type']
    try:
        from equipment_manager import add_equipment as _add_equip
        equip_id = _add_equip(user_id, data)
        # add_equipment returns just an int ID - fetch the full record
        from equipment_manager import get_equipment_by_id as _get_equip
        equipment = _get_equip(equip_id, user_id)

        # --- Auto-create maintenance schedules from seed data ---
        try:
            from equipment_seed_data import SERVICE_INTERVALS
            from equipment_manager import create_maintenance_schedule as _create_sched
            eq_type = data.get('equipment_type', 'other')
            interval_entry = SERVICE_INTERVALS.get(eq_type, {})
            tasks = interval_entry.get('tasks', []) if isinstance(interval_entry, dict) else interval_entry
            for task in tasks:
                sched_data = {
                    'equipment_id': equip_id,
                    'task_description': task['label'],
                    'interval_hours': task.get('interval_hours'),
                    'priority': 'high' if task.get('interval_hours', 999) <= 50 else
                                'medium' if task.get('interval_hours', 999) <= 250 else 'low',
                }
                _create_sched(user_id, sched_data)
            if tasks:
                logger.info(f"Auto-created {len(tasks)} maintenance schedules for equipment {equip_id} ({eq_type})")
        except Exception as sched_err:
            # Don't fail the whole request if schedule creation has an issue
            logger.warning(f"Could not auto-create schedules for equipment {equip_id}: {sched_err}")

        return jsonify(equipment), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating equipment: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/<int:equipment_id>', methods=['GET'])
def get_equipment_by_id(equipment_id):
    user_id = _user_id()
    try:
        from equipment_manager import get_equipment_by_id as _get_equip_by_id
        equipment = _get_equip_by_id(equipment_id, user_id)
        return jsonify(equipment)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting equipment {equipment_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/<int:equipment_id>', methods=['PUT'])
def update_equipment(equipment_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    if 'type' in data and 'equipment_type' not in data:
        data['equipment_type'] = data['type']
    try:
        from equipment_manager import update_equipment as _update_equip
        equipment = _update_equip(equipment_id, user_id, data)
        return jsonify(equipment)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating equipment {equipment_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/<int:equipment_id>', methods=['DELETE'])
def delete_equipment_route(equipment_id):
    user_id = _user_id()
    try:
        from equipment_manager import delete_equipment as _delete_equip
        deleted = _delete_equip(equipment_id, user_id)
        if not deleted:
            return jsonify({'error': 'Equipment not found'}), 404
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting equipment {equipment_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/<int:equipment_id>/maintenance', methods=['GET'])
def get_maintenance_history(equipment_id):
    user_id = _user_id()
    try:
        from equipment_manager import get_maintenance_history as _get_maint
        records = _get_maint(equipment_id, user_id)
        return jsonify(records)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting maintenance history: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/maintenance', methods=['POST'])
def create_maintenance_record():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from equipment_manager import log_maintenance as _log_maint
        record = _log_maint(user_id, data)
        return jsonify(record), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating maintenance record: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/maintenance/upcoming', methods=['GET'])
def get_upcoming_maintenance():
    user_id = _user_id()
    days = request.args.get('days', 30, type=int)
    try:
        from equipment_manager import get_upcoming_maintenance as _get_upcoming
        records = _get_upcoming(user_id, days=days)
        return jsonify(records)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting upcoming maintenance: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/maintenance/overdue', methods=['GET'])
def get_overdue_maintenance():
    user_id = _user_id()
    try:
        from equipment_manager import get_overdue_maintenance as _get_overdue
        records = _get_overdue(user_id)
        return jsonify(records)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting overdue maintenance: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/<int:equipment_id>/hours', methods=['GET'])
def get_equipment_hours(equipment_id):
    user_id = _user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from equipment_manager import get_hours_log as _get_hours
        hours = _get_hours(equipment_id, user_id, start_date=start_date, end_date=end_date)
        return jsonify(hours)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting equipment hours: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/hours', methods=['POST'])
def log_equipment_hours():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from equipment_manager import log_hours as _log_hours
        record = _log_hours(user_id, data)
        return jsonify(record), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error logging equipment hours: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/<int:equipment_id>/calibration', methods=['GET'])
def get_calibration_records(equipment_id):
    user_id = _user_id()
    try:
        from equipment_manager import get_calibration_history as _get_cal
        records = _get_cal(equipment_id, user_id)
        return jsonify(records)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting calibration records: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/calibration', methods=['POST'])
def create_calibration_record():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from equipment_manager import log_calibration as _log_cal
        record = _log_cal(user_id, data)
        return jsonify(record), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating calibration record: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/summary', methods=['GET'])
def get_equipment_summary():
    user_id = _user_id()
    try:
        from equipment_manager import get_fleet_summary as _get_fleet
        summary = _get_fleet(user_id)
        return jsonify(summary)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting equipment summary: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Irrigation API
# Signatures:
#   add_zone(user_id, data)
#   update_zone(zone_id, user_id, data)
#   delete_zone(zone_id, user_id)
#   get_zones(user_id, area=None)
#   get_zone_by_id(zone_id, user_id)
#   log_irrigation_run(user_id, data)
#   get_irrigation_history(user_id, zone_id=None, start_date=None, end_date=None)
#   log_moisture_reading(user_id, data)
#   get_moisture_readings(user_id, zone_id=None, start_date=None, end_date=None)
#   log_et_data(user_id, data)
#   get_water_balance(user_id, zone_id, days=14)
#   get_water_usage(user_id, start_date=None, end_date=None)
#   get_irrigation_recommendation(user_id, zone_id=None)
#   get_drought_status(user_id)
# ====================================================================

@features_bp.route('/api/irrigation/zones', methods=['GET'])
def get_irrigation_zones():
    user_id = _user_id()
    area = request.args.get('area')
    try:
        from irrigation_manager import get_zones as _get_zones
        zones = _get_zones(user_id, area=area)
        return jsonify(zones)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation zones: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/zones', methods=['POST'])
def create_irrigation_zone():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import add_zone as _add_zone
        result = _add_zone(user_id, data)
        if isinstance(result, int):
            from irrigation_manager import get_zone_by_id as _get_zone_by_id
            zone = _get_zone_by_id(result, user_id)
        else:
            zone = result
        return jsonify(zone), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating irrigation zone: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/zones/<int:zone_id>', methods=['GET'])
def get_irrigation_zone_by_id(zone_id):
    user_id = _user_id()
    try:
        from irrigation_manager import get_zone_by_id as _get_zone
        zone = _get_zone(zone_id, user_id)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation zone {zone_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/zones/<int:zone_id>', methods=['PUT'])
def update_irrigation_zone(zone_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import update_zone as _update_zone
        zone = _update_zone(zone_id, user_id, data)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating irrigation zone {zone_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/zones/<int:zone_id>', methods=['DELETE'])
def delete_irrigation_zone(zone_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_zone as _delete_zone
        result = _delete_zone(zone_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting irrigation zone {zone_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/runs', methods=['GET'])
def get_irrigation_runs():
    user_id = _user_id()
    zone_id = request.args.get('zone_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from irrigation_manager import get_irrigation_history as _get_history
        runs = _get_history(user_id, zone_id=zone_id, start_date=start_date, end_date=end_date)
        return jsonify(runs)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation runs: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/runs', methods=['POST'])
def create_irrigation_run():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_irrigation_run as _log_run
        result = _log_run(user_id, data)
        run = {'id': result} if isinstance(result, int) else result
        return jsonify(run), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating irrigation run: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/moisture', methods=['GET'])
def get_moisture_readings():
    user_id = _user_id()
    zone_id = request.args.get('zone_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from irrigation_manager import get_moisture_readings as _get_moisture
        readings = _get_moisture(user_id, zone_id=zone_id, start_date=start_date, end_date=end_date)
        return jsonify(readings)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting moisture readings: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/moisture', methods=['POST'])
def create_moisture_reading():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_moisture_reading as _log_moisture
        result = _log_moisture(user_id, data)
        reading = {'id': result} if isinstance(result, int) else result
        return jsonify(reading), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating moisture reading: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/et', methods=['POST'])
def create_et_entry():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_et_data as _log_et
        result = _log_et(user_id, data)
        entry = {'id': result} if isinstance(result, int) else result
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating ET entry: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/water-usage', methods=['GET'])
def get_water_usage():
    user_id = _user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from irrigation_manager import get_water_usage as _get_usage
        usage = _get_usage(user_id, start_date=start_date, end_date=end_date)
        return jsonify(usage)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water usage: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/recommendations', methods=['GET'])
def get_irrigation_recommendations():
    user_id = _user_id()
    zone_id = request.args.get('zone_id', type=int)
    try:
        from irrigation_manager import get_irrigation_recommendation as _get_rec
        recs = _get_rec(user_id, zone_id=zone_id)
        return jsonify(recs)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/water-balance', methods=['GET'])
def get_water_balance():
    user_id = _user_id()
    zone_id = request.args.get('zone_id', type=int)
    days = request.args.get('days', 14, type=int)
    try:
        from irrigation_manager import get_water_balance as _get_balance
        balance = _get_balance(user_id, zone_id, days=days)
        return jsonify(balance)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water balance: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/drought-status', methods=['GET'])
def get_drought_status():
    user_id = _user_id()
    try:
        from irrigation_manager import get_drought_status as _get_drought
        status = _get_drought(user_id)
        return jsonify(status)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting drought status: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Soil API
# Signatures:
#   add_soil_test(user_id, data)
#   update_soil_test(test_id, user_id, data)
#   delete_soil_test(test_id, user_id)
#   get_soil_tests(user_id, area=None, start_date=None, end_date=None)
#   get_soil_test_by_id(test_id, user_id)
#   generate_amendment_recommendations(test_id, user_id, target_ph=None)
#   get_amendments(test_id, user_id)
#   add_water_test(user_id, data)
#   get_water_tests(user_id)
#   get_water_quality_assessment(test_id, user_id)
#   get_soil_trend(user_id, area, parameter, years=5)
#   get_optimal_ranges(grass_type, area)  [NO user_id!]
# ====================================================================

@features_bp.route('/api/soil/tests', methods=['GET'])
def get_soil_tests():
    user_id = _user_id()
    area = request.args.get('area')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from soil_testing import get_soil_tests as _get_soil
        tests = _get_soil(user_id, area=area, start_date=start_date, end_date=end_date)
        return jsonify([_soil_outbound(t) for t in tests])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil tests: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/tests', methods=['POST'])
def create_soil_test():
    user_id = _user_id()
    data = _soil_inbound(request.get_json(force=True))
    try:
        from soil_testing import add_soil_test as _add_soil
        result = _add_soil(user_id, data)
        if result is None:
            return jsonify({'error': 'Failed to create soil test. Check required fields: test_date, area, ph'}), 400
        # add_soil_test returns bare int ID - fetch full record
        from soil_testing import get_soil_test_by_id as _get_soil_by_id
        test = _get_soil_by_id(result, user_id)
        return jsonify(_soil_outbound(test)), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating soil test: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/tests/<int:test_id>', methods=['GET'])
def get_soil_test_by_id(test_id):
    user_id = _user_id()
    try:
        from soil_testing import get_soil_test_by_id as _get_soil_by_id
        test = _get_soil_by_id(test_id, user_id)
        return jsonify(_soil_outbound(test))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil test {test_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/tests/<int:test_id>', methods=['PUT'])
def update_soil_test(test_id):
    user_id = _user_id()
    data = _soil_inbound(request.get_json(force=True))
    try:
        from soil_testing import update_soil_test as _update_soil
        test = _update_soil(test_id, user_id, data)
        return jsonify(_soil_outbound(test))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating soil test {test_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/tests/<int:test_id>', methods=['DELETE'])
def delete_soil_test(test_id):
    user_id = _user_id()
    try:
        from soil_testing import delete_soil_test as _delete_soil
        result = _delete_soil(test_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting soil test {test_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/tests/<int:test_id>/amendments', methods=['GET'])
def get_soil_amendments(test_id):
    user_id = _user_id()
    try:
        from soil_testing import get_amendments as _get_amend
        amendments = _get_amend(test_id, user_id)
        return jsonify(amendments)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil amendments: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/tests/<int:test_id>/amendments/generate', methods=['POST'])
def generate_amendment_recommendations(test_id):
    user_id = _user_id()
    data = request.get_json(silent=True) or {}
    target_ph = data.get('target_ph')
    try:
        from soil_testing import generate_amendment_recommendations as _gen_amend
        result = _gen_amend(test_id, user_id, target_ph=target_ph)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating amendment recommendations for test {test_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/water-tests', methods=['GET'])
def get_water_tests():
    user_id = _user_id()
    try:
        from soil_testing import get_water_tests as _get_water
        tests = _get_water(user_id)
        return jsonify(tests)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water tests: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/water-tests', methods=['POST'])
def create_water_test():
    user_id = _user_id()
    data = _water_inbound(request.get_json(force=True))
    try:
        from soil_testing import add_water_test as _add_water
        result = _add_water(user_id, data)
        if result is None:
            return jsonify({'error': 'Failed to create water test. Check required field: test_date'}), 400
        from soil_testing import get_water_test_by_id as _get_wt
        test = _get_wt(result, user_id)
        return jsonify(test), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating water test: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/water-tests/<int:test_id>/assessment', methods=['GET'])
def get_water_quality_assessment(test_id):
    user_id = _user_id()
    try:
        from soil_testing import get_water_quality_assessment as _get_wqa
        assessment = _get_wqa(test_id, user_id)
        return jsonify(assessment)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water quality assessment {test_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/trends', methods=['GET'])
def get_soil_trends():
    user_id = _user_id()
    area = request.args.get('area')
    parameter = request.args.get('parameter')
    years = request.args.get('years', 5, type=int)
    try:
        from soil_testing import get_soil_trend as _get_trend
        trends = _get_trend(user_id, area, parameter, years=years)
        return jsonify(trends)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil trends: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/optimal-ranges', methods=['GET'])
def get_optimal_ranges():
    grass_type = request.args.get('grass_type')
    area = request.args.get('area')
    try:
        from soil_testing import get_optimal_ranges as _get_ranges
        ranges = _get_ranges(grass_type, area)
        return jsonify(ranges)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting optimal ranges: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Community API
# Signatures:
#   create_post(user_id, data)
#   get_posts(category=None, page=1, per_page=20)  [NO user_id!]
#   get_post_by_id(post_id)  [NO user_id!]
#   create_reply(post_id, user_id, content)
#   upvote_post(post_id, user_id)
#   create_alert(user_id, data)
#   get_alerts(region=None, state=None, alert_type=None, active_only=True)  [NO user_id!]
#   vote_alert(alert_id, user_id, vote_type)
#   share_program(user_id, data)
#   get_shared_programs(program_type=None, region=None, grass_type=None)  [NO user_id!]
#   rate_program(program_id, user_id, rating, comment=None)
#   download_program(program_id, user_id)
#   submit_benchmark(user_id, data)
#   get_benchmarks(region=None, grass_type=None, course_type=None, ...)
#   get_my_vs_peers(user_id, metric_type, year=None)
# ====================================================================

@features_bp.route('/api/community/posts', methods=['GET'])
def get_community_posts():
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    try:
        from community import get_posts as _get_posts
        posts = _get_posts(category=category, page=page, per_page=per_page)
        return jsonify(posts)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community posts: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/posts', methods=['POST'])
def create_community_post():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import create_post as _create_post
        result = _create_post(user_id, data)
        if isinstance(result, int):
            from community import get_post_by_id as _get_post
            post = _get_post(result)
        else:
            post = result
        return jsonify(post), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating community post: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/posts/<int:post_id>', methods=['GET'])
def get_community_post_by_id(post_id):
    try:
        from community import get_post_by_id as _get_post
        post = _get_post(post_id)
        return jsonify(post)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/posts/<int:post_id>/replies', methods=['POST'])
@features_bp.route('/api/community/posts/<int:post_id>/reply', methods=['POST'])
def reply_to_community_post(post_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    content = data.get('content', '')
    try:
        from community import create_reply as _create_reply
        result = _create_reply(post_id, user_id, content)
        reply = {'id': result, 'post_id': post_id, 'content': content} if isinstance(result, int) else result
        return jsonify(reply), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error replying to community post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/posts/<int:post_id>/vote', methods=['POST'])
@features_bp.route('/api/community/posts/<int:post_id>/upvote', methods=['POST'])
def upvote_community_post(post_id):
    user_id = _user_id()
    try:
        from community import upvote_post as _upvote
        result = _upvote(post_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error upvoting community post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/posts/<int:post_id>', methods=['DELETE'])
def delete_community_post(post_id):
    user_id = _user_id()
    try:
        from community import delete_post as _delete_post
        result = _check_error(_delete_post(post_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting community post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/alerts/<int:alert_id>', methods=['DELETE'])
def delete_community_alert(alert_id):
    user_id = _user_id()
    try:
        from community import delete_alert as _delete_alert
        result = _check_error(_delete_alert(alert_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting community alert {alert_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/alerts', methods=['GET'])
def get_community_alerts():
    region = request.args.get('region')
    state = request.args.get('state')
    alert_type = request.args.get('type')
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    try:
        from community import get_alerts as _get_alerts
        alerts = _get_alerts(region=region, state=state, alert_type=alert_type, active_only=active_only)
        return jsonify(alerts)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community alerts: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/alerts', methods=['POST'])
def create_community_alert():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import create_alert as _create_alert
        result = _create_alert(user_id, data)
        alert = {'id': result} if isinstance(result, int) else result
        return jsonify(alert), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating community alert: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/alerts/<int:alert_id>/verify', methods=['POST'])
@features_bp.route('/api/community/alerts/<int:alert_id>/vote', methods=['POST'])
def vote_community_alert(alert_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    vote_type = data.get('vote_type', '')
    try:
        from community import vote_alert as _vote_alert
        result = _vote_alert(alert_id, user_id, vote_type)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error voting on community alert {alert_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/programs', methods=['GET'])
def get_community_programs():
    program_type = request.args.get('program_type')
    region = request.args.get('region')
    grass_type = request.args.get('grass_type')
    try:
        from community import get_shared_programs as _get_programs
        programs = _get_programs(program_type=program_type, region=region, grass_type=grass_type)
        return jsonify(programs)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community programs: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/programs', methods=['POST'])
def create_community_program():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import share_program as _share_program
        result = _share_program(user_id, data)
        program = {'id': result} if isinstance(result, int) else result
        return jsonify(program), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating community program: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/programs/<int:program_id>/rate', methods=['POST'])
def rate_community_program(program_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    rating = data.get('rating')
    comment = data.get('comment')
    try:
        from community import rate_program as _rate_program
        result = _rate_program(program_id, user_id, rating, comment=comment)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error rating community program {program_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/programs/<int:program_id>/download', methods=['GET'])
def download_community_program(program_id):
    user_id = _user_id()
    try:
        from community import download_program as _download
        result = _download(program_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error downloading community program {program_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/benchmarks', methods=['GET'])
def get_community_benchmarks():
    region = request.args.get('region')
    grass_type = request.args.get('grass_type')
    course_type = request.args.get('course_type')
    try:
        from community import get_benchmarks as _get_benchmarks
        benchmarks = _get_benchmarks(region=region, grass_type=grass_type, course_type=course_type)
        return jsonify(benchmarks)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community benchmarks: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/benchmarks', methods=['POST'])
def submit_community_benchmark():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import submit_benchmark as _submit_bench
        result = _submit_bench(user_id, data)
        benchmark = {'id': result} if isinstance(result, int) else result
        return jsonify(benchmark), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error submitting community benchmark: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/community/benchmarks/compare', methods=['GET'])
def compare_community_benchmarks():
    user_id = _user_id()
    metric_type = request.args.get('metric_type')
    year = request.args.get('year', type=int)
    try:
        from community import get_my_vs_peers as _compare
        comparison = _compare(user_id, metric_type, year=year)
        return jsonify(comparison)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error comparing community benchmarks: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Cultivar API
# Signatures:
#   search_cultivars(species=None, category=None, region=None, min_quality=None)  [NO user_id!]
#   compare_cultivars(cultivar_names, criteria_weights=None)  [NO user_id!]
#   recommend_cultivars(user_requirements)  [NO user_id!]
#   get_renovation_projects(user_id)
#   create_renovation_project(user_id, data)
#   update_renovation_project(project_id, user_id, data)
#   get_blend_recommendation(species, category=None, region=None)  [NO user_id!]
#   calculate_seeding_rate(cultivar_name, method='seed', area_sqft=1000.0)  [NO user_id!]
# ====================================================================

@features_bp.route('/api/cultivars/search', methods=['GET'])
def search_cultivars():
    species = request.args.get('species')
    category = request.args.get('category')
    region = request.args.get('region')
    min_quality = request.args.get('min_quality', type=float)
    try:
        from cultivar_tool import search_cultivars as _search
        results = _search(species=species, category=category, region=region, min_quality=min_quality)
        return jsonify(results)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error searching cultivars: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/compare', methods=['POST'])
def compare_cultivars():
    data = request.get_json(force=True)
    cultivar_names = data.get('cultivar_names', [])
    criteria_weights = data.get('criteria_weights')
    try:
        from cultivar_tool import compare_cultivars as _compare
        comparison = _compare(cultivar_names, criteria_weights=criteria_weights)
        return jsonify(comparison)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error comparing cultivars: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/recommend', methods=['POST'])
def recommend_cultivars():
    data = request.get_json(force=True)
    try:
        from cultivar_tool import recommend_cultivars as _recommend
        recommendations = _recommend(data)
        return jsonify(recommendations)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting cultivar recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/renovation', methods=['GET'])
def get_renovation_plans():
    user_id = _user_id()
    try:
        from cultivar_tool import get_renovation_projects as _get_projects
        plans = _get_projects(user_id)
        return jsonify(plans)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting renovation plans: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/renovation', methods=['POST'])
def create_renovation_plan():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from cultivar_tool import create_renovation_project as _create_project
        plan = _create_project(user_id, data)
        return jsonify(plan), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating renovation plan: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/renovation/<int:plan_id>', methods=['PUT'])
def update_renovation_plan(plan_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from cultivar_tool import update_renovation_project as _update_project
        plan = _update_project(plan_id, user_id, data)
        return jsonify(plan)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating renovation plan {plan_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/blend', methods=['GET'])
def get_cultivar_blend():
    species = request.args.get('species')
    category = request.args.get('category')
    region = request.args.get('region')
    try:
        from cultivar_tool import get_blend_recommendation as _get_blend
        blend = _get_blend(species, category=category, region=region)
        return jsonify(blend)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting cultivar blend: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/cultivars/seeding-rate', methods=['GET'])
def get_seeding_rate():
    cultivar_name = request.args.get('cultivar')
    method = request.args.get('method', 'seed')
    area_sqft = request.args.get('area_sqft', 1000.0, type=float)
    try:
        from cultivar_tool import calculate_seeding_rate as _calc_rate
        rate = _calc_rate(cultivar_name, method=method, area_sqft=area_sqft)
        return jsonify(rate)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting seeding rate: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Notifications API
# Signatures:
#   get_notifications(user_id, unread_only=False, limit=50)
#   mark_read(notification_id, user_id)
#   mark_all_read(user_id)
#   dismiss_notification(notification_id, user_id)
#   get_unread_count(user_id)
#   get_preferences(user_id)
#   update_preference(user_id, notification_type, enabled=None, email_enabled=None, push_enabled=None)
#   create_rule(user_id, data)
#   get_rules(user_id)
#   update_rule(rule_id, user_id, data)
#   delete_rule(rule_id, user_id)
# ====================================================================

@features_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = _user_id()
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = request.args.get('limit', 50, type=int)
    try:
        from notifications import get_notifications as _get_notifs
        notifs = _get_notifs(user_id, unread_only=unread_only, limit=limit)
        return jsonify(notifs)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    user_id = _user_id()
    try:
        from notifications import mark_read as _mark_read
        result = _mark_read(notification_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/read-all', methods=['POST'])
def mark_all_notifications_read():
    user_id = _user_id()
    try:
        from notifications import mark_all_read as _mark_all
        result = _mark_all(user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/<int:notification_id>/dismiss', methods=['POST'])
def dismiss_notification(notification_id):
    user_id = _user_id()
    try:
        from notifications import dismiss_notification as _dismiss
        result = _dismiss(notification_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error dismissing notification {notification_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/unread-count', methods=['GET'])
def get_unread_count():
    user_id = _user_id()
    try:
        from notifications import get_unread_count as _unread
        count = _unread(user_id)
        return jsonify(count)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/preferences', methods=['GET'])
def get_notification_preferences():
    user_id = _user_id()
    try:
        from notifications import get_preferences as _get_prefs
        prefs = _get_prefs(user_id)
        return jsonify(prefs)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting notification preferences: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/preferences', methods=['PUT'])
def update_notification_preferences():
    user_id = _user_id()
    data = request.get_json(force=True)
    notification_type = data.get('notification_type')
    enabled = data.get('enabled')
    email_enabled = data.get('email_enabled')
    push_enabled = data.get('push_enabled')
    try:
        from notifications import update_preference as _update_pref
        prefs = _update_pref(user_id, notification_type, enabled=enabled, email_enabled=email_enabled, push_enabled=push_enabled)
        return jsonify(prefs)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating notification preferences: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/rules', methods=['GET'])
def get_notification_rules():
    user_id = _user_id()
    try:
        from notifications import get_rules as _get_rules
        rules = _get_rules(user_id)
        return jsonify(rules)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting notification rules: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/rules', methods=['POST'])
def create_notification_rule():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from notifications import create_rule as _create_rule
        rule = _create_rule(user_id, data)
        return jsonify(rule), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating notification rule: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/rules/<int:rule_id>', methods=['PUT'])
def update_notification_rule(rule_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from notifications import update_rule as _update_rule
        rule = _update_rule(rule_id, user_id, data)
        return jsonify(rule)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating notification rule {rule_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/notifications/rules/<int:rule_id>', methods=['DELETE'])
def delete_notification_rule(rule_id):
    user_id = _user_id()
    try:
        from notifications import delete_rule as _delete_rule
        result = _delete_rule(rule_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting notification rule {rule_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Reports API
# Signatures:
#   generate_monthly_report(user_id, year, month)
#   generate_green_committee_report(user_id, year, month)
#   generate_annual_report(user_id, year)
#   generate_pesticide_compliance_report(user_id, year)
#   save_report(user_id, data)
#   get_reports(user_id, report_type=None)
#   get_report_by_id(report_id, user_id)
#   delete_report(report_id, user_id)
#   export_report_html(report_id, user_id)
#   log_compliance_record(user_id, data)
#   get_compliance_records(user_id, record_type=None, year=None)
#   check_compliance_gaps(user_id, year)
# ====================================================================

@features_bp.route('/api/reports/generate', methods=['POST'])
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


@features_bp.route('/api/reports/save', methods=['POST'])
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


@features_bp.route('/api/reports/list', methods=['GET'])
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


@features_bp.route('/api/reports/list/<int:report_id>', methods=['GET'])
@features_bp.route('/api/reports/<int:report_id>', methods=['GET'])
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


@features_bp.route('/api/reports/list/<int:report_id>', methods=['DELETE'])
@features_bp.route('/api/reports/<int:report_id>', methods=['DELETE'])
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


@features_bp.route('/api/reports/export/<int:report_id>', methods=['GET'])
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


@features_bp.route('/api/reports/compliance', methods=['GET'])
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


@features_bp.route('/api/reports/compliance', methods=['POST'])
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


@features_bp.route('/api/reports/compliance/gap-check', methods=['GET'])
@features_bp.route('/api/reports/compliance/gaps', methods=['GET'])
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


# ====================================================================
# Calculator API
# Signatures:
#   convert_rate(value, from_rate, to_rate)  [NO user_id!]
#   calculate_gpa(speed_mph, nozzle_spacing_inches, flow_rate_gpm)  [NO user_id!]
#   calculate_product_rate_for_target_n(target_n_rate, npk_analysis, area_sqft=1000)  [NO user_id!]
#   calculate_gdd(tmax, tmin, base=50, cap=86)  [NO user_id!]
# ====================================================================

@features_bp.route('/api/calculator/convert-rate', methods=['POST'])
def convert_rate():
    data = request.get_json(force=True)
    value = data.get('value')
    from_rate = data.get('from_rate')
    to_rate = data.get('to_rate')
    try:
        from unit_converter import convert_rate as _convert
        result = _convert(value, from_rate, to_rate)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error converting rate: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calculator/spray', methods=['POST'])
def calculate_spray():
    data = request.get_json(force=True)
    speed_mph = data.get('speed_mph')
    nozzle_spacing_inches = data.get('nozzle_spacing_inches')
    flow_rate_gpm = data.get('flow_rate_gpm')
    try:
        from unit_converter import calculate_gpa as _calc_gpa
        result = _calc_gpa(speed_mph, nozzle_spacing_inches, flow_rate_gpm)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error calculating spray: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calculator/fertilizer', methods=['POST'])
def calculate_fertilizer():
    data = request.get_json(force=True)
    target_n_rate = data.get('target_n_rate')
    npk_analysis = data.get('npk_analysis')
    area_sqft = data.get('area_sqft', 1000)
    try:
        from unit_converter import calculate_product_rate_for_target_n as _calc_fert
        result = _calc_fert(target_n_rate, npk_analysis, area_sqft=area_sqft)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error calculating fertilizer: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/calculator/gdd', methods=['POST'])
def calculate_gdd():
    data = request.get_json(force=True)
    tmax = data.get('tmax')
    tmin = data.get('tmin')
    base = data.get('base', 50)
    cap = data.get('cap', 86)
    try:
        from unit_converter import calculate_gdd as _calc_gdd
        result = _calc_gdd(tmax, tmin, base=base, cap=cap)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error calculating GDD: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# Course Map API
# Signatures:
#   create_zone(user_id, data)
#   update_zone(zone_id, user_id, data)
#   delete_zone(zone_id, user_id)
#   get_zones(user_id, zone_type=None)
#   get_zone_by_id(zone_id, user_id)
#   get_zones_geojson(user_id)
#   create_pin(user_id, data)
#   update_pin(pin_id, user_id, data)
#   delete_pin(pin_id, user_id)
#   get_pins(user_id, pin_type=None, zone_id=None, status=None)
#   get_pins_geojson(user_id, pin_type=None)
#   create_layer(user_id, data)
#   update_layer(layer_id, user_id, data)
#   delete_layer(layer_id, user_id)
#   get_layers(user_id)
# ====================================================================

@features_bp.route('/api/map/zones', methods=['GET'])
def get_map_zones():
    user_id = _user_id()
    zone_type = request.args.get('type')
    try:
        from course_map import get_zones as _get_map_zones
        zones = _get_map_zones(user_id, zone_type=zone_type)
        return jsonify(zones)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map zones: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/zones', methods=['POST'])
def create_map_zone():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import create_zone as _create_map_zone
        zone = _create_map_zone(user_id, data)
        return jsonify(zone), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating map zone: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/zones/<int:zone_id>', methods=['GET'])
def get_map_zone_by_id(zone_id):
    user_id = _user_id()
    try:
        from course_map import get_zone_by_id as _get_zone
        zone = _get_zone(zone_id, user_id)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map zone {zone_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/zones/<int:zone_id>', methods=['PUT'])
def update_map_zone(zone_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import update_zone as _update_map_zone
        zone = _update_map_zone(zone_id, user_id, data)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating map zone {zone_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/zones/<int:zone_id>', methods=['DELETE'])
def delete_map_zone(zone_id):
    user_id = _user_id()
    try:
        from course_map import delete_zone as _delete_map_zone
        result = _delete_map_zone(zone_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting map zone {zone_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/zones/geojson', methods=['GET'])
def get_zones_geojson():
    user_id = _user_id()
    try:
        from course_map import get_zones_geojson as _get_geojson
        geojson = _get_geojson(user_id)
        return jsonify(geojson)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting zones GeoJSON: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/pins', methods=['GET'])
def get_map_pins():
    user_id = _user_id()
    pin_type = request.args.get('type')
    zone_id = request.args.get('zone_id', type=int)
    status = request.args.get('status')
    try:
        from course_map import get_pins as _get_pins
        pins = _get_pins(user_id, pin_type=pin_type, zone_id=zone_id, status=status)
        return jsonify(pins)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map pins: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/pins', methods=['POST'])
def create_map_pin():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import create_pin as _create_pin
        pin = _create_pin(user_id, data)
        return jsonify(pin), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating map pin: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/pins/<int:pin_id>', methods=['PUT'])
def update_map_pin(pin_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import update_pin as _update_pin
        pin = _update_pin(pin_id, user_id, data)
        return jsonify(pin)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating map pin {pin_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/pins/<int:pin_id>', methods=['DELETE'])
def delete_map_pin(pin_id):
    user_id = _user_id()
    try:
        from course_map import delete_pin as _delete_pin
        result = _delete_pin(pin_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting map pin {pin_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/pins/geojson', methods=['GET'])
def get_pins_geojson():
    user_id = _user_id()
    pin_type = request.args.get('type')
    try:
        from course_map import get_pins_geojson as _get_pins_geo
        geojson = _get_pins_geo(user_id, pin_type=pin_type)
        return jsonify(geojson)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting pins GeoJSON: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/layers', methods=['GET'])
def get_map_layers():
    user_id = _user_id()
    try:
        from course_map import get_layers as _get_layers
        layers = _get_layers(user_id)
        return jsonify(layers)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map layers: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/layers', methods=['POST'])
def create_map_layer():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import create_layer as _create_layer
        layer = _create_layer(user_id, data)
        return jsonify(layer), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating map layer: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/layers/<int:layer_id>', methods=['PUT'])
def update_map_layer(layer_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import update_layer as _update_layer
        layer = _update_layer(layer_id, user_id, data)
        return jsonify(layer)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating map layer {layer_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/map/layers/<int:layer_id>', methods=['DELETE'])
def delete_map_layer(layer_id):
    user_id = _user_id()
    try:
        from course_map import delete_layer as _delete_layer
        result = _delete_layer(layer_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting map layer {layer_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ====================================================================
# ADDITIONAL ROUTES - Template-required endpoints not in original build
# ====================================================================

# --- Equipment: GET all maintenance/hours/calibration (no equipment_id) ---

@features_bp.route('/api/equipment/maintenance', methods=['GET'])
def get_all_maintenance():
    user_id = _user_id()
    try:
        from equipment_manager import get_all_maintenance as _get_all_maint
        records = _get_all_maint(user_id)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Error getting all maintenance: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/hours', methods=['GET'])
def get_all_hours():
    user_id = _user_id()
    try:
        from equipment_manager import get_all_hours as _get_all_hours
        records = _get_all_hours(user_id)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Error getting all hours: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/equipment/calibration', methods=['GET'])
def get_all_calibration():
    user_id = _user_id()
    try:
        from equipment_manager import get_all_calibration as _get_all_cal
        records = _get_all_cal(user_id)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Error getting all calibration: {e}")
        return jsonify({'error': str(e)}), 500


# --- Budget: Line Items CRUD ---

@features_bp.route('/api/budget/budgets/<int:budget_id>/line-items', methods=['GET'])
def get_line_items(budget_id):
    user_id = _user_id()
    try:
        from budget_tracker import get_line_items as _get_items
        items = _get_items(budget_id, user_id)
        return jsonify(items)
    except Exception as e:
        logger.error(f"Error getting line items: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/budgets/<int:budget_id>/line-items', methods=['POST'])
def create_line_item(budget_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from budget_tracker import create_line_item as _create_item
        item = _create_item(budget_id, user_id, data)
        return jsonify(item), 201
    except Exception as e:
        logger.error(f"Error creating line item: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/budget/budgets/<int:budget_id>/line-items/<int:item_id>', methods=['DELETE'])
def delete_line_item(budget_id, item_id):
    user_id = _user_id()
    try:
        from budget_tracker import delete_line_item as _del_item
        result = _del_item(budget_id, item_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting line item: {e}")
        return jsonify({'error': str(e)}), 500


# --- Budget: GET individual purchase order ---

@features_bp.route('/api/budget/purchase-orders/<int:po_id>', methods=['GET'])
def get_purchase_order(po_id):
    user_id = _user_id()
    try:
        from budget_tracker import get_purchase_order_by_id as _get_po
        po = _get_po(po_id, user_id)
        return jsonify(po)
    except Exception as e:
        logger.error(f"Error getting purchase order {po_id}: {e}")
        return jsonify({'error': str(e)}), 500


# --- Crew: Daily Assignment PUT/DELETE ---

@features_bp.route('/api/crew/daily-assignments/<int:assignment_id>', methods=['PUT'])
def update_daily_assignment(assignment_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from crew_management import update_assignment as _update_assign
        result = _update_assign(assignment_id, user_id, data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating assignment {assignment_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/crew/daily-assignments/<int:assignment_id>', methods=['DELETE'])
def delete_daily_assignment(assignment_id):
    user_id = _user_id()
    try:
        from crew_management import delete_assignment as _del_assign
        result = _del_assign(assignment_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting assignment {assignment_id}: {e}")
        return jsonify({'error': str(e)}), 500


# --- Irrigation: Missing DELETE/GET/POST routes ---

@features_bp.route('/api/irrigation/runs/<int:run_id>', methods=['DELETE'])
def delete_irrigation_run(run_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_irrigation_run as _del_run
        result = _del_run(run_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting irrigation run {run_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/moisture/<int:reading_id>', methods=['DELETE'])
def delete_moisture_reading(reading_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_moisture_reading as _del_moisture
        result = _del_moisture(reading_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting moisture reading {reading_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/water-usage', methods=['POST'])
def log_water_usage():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_water_usage as _log_usage
        result = _log_usage(user_id, data)
        usage = {'id': result} if isinstance(result, int) else result
        return jsonify(usage), 201
    except Exception as e:
        logger.error(f"Error logging water usage: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/water-usage/<int:usage_id>', methods=['DELETE'])
def delete_water_usage(usage_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_water_usage as _del_usage
        result = _del_usage(usage_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting water usage {usage_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/irrigation/et', methods=['GET'])
def get_et_data():
    user_id = _user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        from irrigation_manager import get_et_data as _get_et
        data = _get_et(user_id, start_date=start_date, end_date=end_date)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting ET data: {e}")
        return jsonify({'error': str(e)}), 500


# --- Soil: Missing routes ---

@features_bp.route('/api/soil/amendments', methods=['GET'])
def get_all_amendments():
    user_id = _user_id()
    area = request.args.get('area')
    try:
        from soil_testing import get_all_amendments as _get_amend
        amendments = _get_amend(user_id, area=area)
        return jsonify(amendments)
    except Exception as e:
        logger.error(f"Error getting amendments: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/amendments/<int:amendment_id>/apply', methods=['POST'])
def apply_amendment(amendment_id):
    user_id = _user_id()
    try:
        from soil_testing import apply_amendment as _apply_amend
        result = _apply_amend(amendment_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error applying amendment {amendment_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/soil/water-tests/<int:test_id>', methods=['DELETE'])
def delete_water_test(test_id):
    user_id = _user_id()
    try:
        from soil_testing import delete_water_test as _del_water
        result = _del_water(test_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting water test {test_id}: {e}")
        return jsonify({'error': str(e)}), 500


# --- Cultivars: Renovation DELETE ---

@features_bp.route('/api/cultivars/renovation/<int:plan_id>', methods=['DELETE'])
def delete_renovation_project(plan_id):
    user_id = _user_id()
    try:
        from cultivar_tool import delete_renovation_project as _del_reno
        result = _del_reno(plan_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting renovation project {plan_id}: {e}")
        return jsonify({'error': str(e)}), 500


# --- Reports: Missing routes ---

@features_bp.route('/api/reports/generate', methods=['GET'])
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


@features_bp.route('/api/reports/export', methods=['GET'])
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


@features_bp.route('/api/reports/compliance/<int:record_id>', methods=['DELETE'])
def delete_compliance_record(record_id):
    user_id = _user_id()
    try:
        from reporting import delete_compliance_record as _del_compliance
        result = _del_compliance(record_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting compliance record {record_id}: {e}")
        return jsonify({'error': str(e)}), 500


@features_bp.route('/api/reports/compliance/export', methods=['GET'])
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


# --- Scouting: Individual template GET ---

@features_bp.route('/api/scouting/templates/<int:template_id>', methods=['GET'])
def get_scouting_template(template_id):
    user_id = _user_id()
    try:
        from scouting_log import get_scouting_template_by_id as _get_tmpl
        template = _get_tmpl(template_id, user_id)
        return jsonify(template)
    except Exception as e:
        logger.error(f"Error getting scouting template {template_id}: {e}")
        return jsonify({'error': str(e)}), 500


# --- Course Map: Individual layer GET ---

@features_bp.route('/api/map/layers/<path:layer_name>', methods=['GET'])
def get_map_layer_by_name(layer_name):
    user_id = _user_id()
    try:
        from course_map import get_layer_by_name as _get_layer
        layer = _get_layer(user_id, layer_name)
        return jsonify(layer)
    except Exception as e:
        logger.error(f"Error getting map layer {layer_name}: {e}")
        return jsonify({'error': str(e)}), 500
