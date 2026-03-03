"""Equipment API blueprint."""

from flask import Blueprint, jsonify, request, render_template
import logging

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

equipment_bp = Blueprint('equipment_bp', __name__)


# ====================================================================
# Page Route
# ====================================================================

@equipment_bp.route('/equipment')
def equipment_page():
    return render_template('equipment.html')


# ====================================================================
# Equipment API
# ====================================================================

# -- Seed-data endpoints (manufacturers, models, service intervals) --

@equipment_bp.route('/api/equipment/seed/manufacturers', methods=['GET'])
def get_manufacturers():
    """Return the full list of known equipment manufacturers."""
    try:
        from equipment_seed_data import MANUFACTURERS
        return jsonify(MANUFACTURERS)
    except Exception as e:
        logger.error(f"Error getting manufacturers: {e}")
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/api/equipment/seed/models', methods=['GET'])
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


@equipment_bp.route('/api/equipment/seed/service-intervals', methods=['GET'])
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


@equipment_bp.route('/api/equipment', methods=['GET'])
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


@equipment_bp.route('/api/equipment', methods=['POST'])
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


@equipment_bp.route('/api/equipment/<int:equipment_id>', methods=['GET'])
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


@equipment_bp.route('/api/equipment/<int:equipment_id>', methods=['PUT'])
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


@equipment_bp.route('/api/equipment/<int:equipment_id>', methods=['DELETE'])
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


@equipment_bp.route('/api/equipment/<int:equipment_id>/maintenance', methods=['GET'])
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


@equipment_bp.route('/api/equipment/maintenance', methods=['POST'])
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


@equipment_bp.route('/api/equipment/maintenance', methods=['GET'])
def get_all_maintenance():
    user_id = _user_id()
    try:
        from equipment_manager import get_all_maintenance as _get_all_maint
        records = _get_all_maint(user_id)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Error getting all maintenance: {e}")
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/api/equipment/maintenance/upcoming', methods=['GET'])
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


@equipment_bp.route('/api/equipment/maintenance/overdue', methods=['GET'])
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


@equipment_bp.route('/api/equipment/<int:equipment_id>/hours', methods=['GET'])
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


@equipment_bp.route('/api/equipment/hours', methods=['POST'])
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


@equipment_bp.route('/api/equipment/hours', methods=['GET'])
def get_all_hours():
    user_id = _user_id()
    try:
        from equipment_manager import get_all_hours as _get_all_hours
        records = _get_all_hours(user_id)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Error getting all hours: {e}")
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/api/equipment/<int:equipment_id>/calibration', methods=['GET'])
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


@equipment_bp.route('/api/equipment/calibration', methods=['POST'])
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


@equipment_bp.route('/api/equipment/calibration', methods=['GET'])
def get_all_calibration():
    user_id = _user_id()
    try:
        from equipment_manager import get_all_calibration as _get_all_cal
        records = _get_all_cal(user_id)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Error getting all calibration: {e}")
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/api/equipment/summary', methods=['GET'])
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


@equipment_bp.route('/api/equipment/export', methods=['GET'])
def export_equipment():
    """Export equipment inventory as CSV or PDF."""
    user_id = _user_id()
    fmt = request.args.get('format', 'csv').lower()
    try:
        from equipment_manager import get_equipment as _get_equipment
        items = _get_equipment(user_id)
        columns = [
            ('name', 'Name'),
            ('equipment_type', 'Type'),
            ('manufacturer', 'Manufacturer'),
            ('model', 'Model'),
            ('year', 'Year'),
            ('serial_number', 'Serial Number'),
            ('status', 'Status'),
            ('hours', 'Hours'),
        ]
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
        if fmt == 'pdf':
            from export_service import export_pdf
            return export_pdf(items, 'Equipment Inventory', columns, f'equipment_{date_str}.pdf')
        from export_service import export_csv
        return export_csv(items, columns, f'equipment_{date_str}.csv')
    except Exception as e:
        logger.error(f"Error exporting equipment: {e}")
        return jsonify({'error': str(e)}), 500
