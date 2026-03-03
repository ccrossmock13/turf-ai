"""Calendar API blueprint."""

from flask import Blueprint, jsonify, request, render_template
import logging

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

calendar_bp = Blueprint('calendar_bp', __name__)


# ====================================================================
# Page Route
# ====================================================================

@calendar_bp.route('/calendar')
def calendar_page():
    return render_template('calendar.html')


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

@calendar_bp.route('/api/calendar/events', methods=['GET'])
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


@calendar_bp.route('/api/calendar/events', methods=['POST'])
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


@calendar_bp.route('/api/calendar/events/<int:event_id>', methods=['GET'])
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


@calendar_bp.route('/api/calendar/events/<int:event_id>', methods=['PUT'])
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


@calendar_bp.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
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


@calendar_bp.route('/api/calendar/events/<int:event_id>/complete', methods=['POST'])
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


@calendar_bp.route('/api/calendar/upcoming', methods=['GET'])
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


@calendar_bp.route('/api/calendar/overdue', methods=['GET'])
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


@calendar_bp.route('/api/calendar/templates', methods=['GET'])
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


@calendar_bp.route('/api/calendar/templates', methods=['POST'])
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


@calendar_bp.route('/api/calendar/templates/apply', methods=['POST'])
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
