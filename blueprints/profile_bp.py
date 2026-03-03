"""Course profile blueprint — extracted from app.py."""

from flask import Blueprint, render_template, jsonify, request, session
from auth import login_required
from profile import (
    get_profile, save_profile, build_profile_context,
    get_profiles, set_active_profile, duplicate_profile, delete_profile,
    get_profile_templates, create_from_template
)

profile = Blueprint('profile', __name__)

# -----------------------------------------------------------------------------
# Course profile routes
# -----------------------------------------------------------------------------

@profile.route('/profile')
@login_required
def profile_page():
    return render_template('profile.html')


@profile.route('/api/profile', methods=['GET'])
@login_required
def api_get_profile():
    """Get profile, optionally by course_name query param."""
    course_name = request.args.get('course_name')
    prof = get_profile(session['user_id'], course_name=course_name)
    return jsonify(prof or {})


@profile.route('/api/profile', methods=['POST'])
@login_required
def api_save_profile():
    data = request.json or {}
    save_profile(session['user_id'], data)
    return jsonify({'success': True})


@profile.route('/api/profile/context-preview')
@login_required
def api_profile_context_preview():
    """Return the AI context string so users can see what the AI 'sees'."""
    context = build_profile_context(session['user_id'])
    return jsonify({'context': context})


@profile.route('/api/profiles', methods=['GET'])
@login_required
def api_list_profiles():
    """List all course profiles for the current user."""
    profiles = get_profiles(session['user_id'])
    return jsonify([{'course_name': p.get('course_name', 'My Course'),
                     'is_active': p.get('is_active', 0),
                     'turf_type': p.get('turf_type'),
                     'city': p.get('city'),
                     'state': p.get('state'),
                     'updated_at': p.get('updated_at')} for p in profiles])


@profile.route('/api/profiles/activate', methods=['POST'])
@login_required
def api_activate_profile():
    """Switch active course profile."""
    data = request.json or {}
    course_name = data.get('course_name')
    if not course_name:
        return jsonify({'error': 'course_name required'}), 400
    success = set_active_profile(session['user_id'], course_name)
    return jsonify({'success': success})


@profile.route('/api/profiles/duplicate', methods=['POST'])
@login_required
def api_duplicate_profile():
    """Duplicate an existing profile under a new name."""
    data = request.json or {}
    source = data.get('source')
    new_name = data.get('new_name')
    if not source or not new_name:
        return jsonify({'error': 'source and new_name required'}), 400
    success = duplicate_profile(session['user_id'], source, new_name)
    return jsonify({'success': success})


@profile.route('/api/profiles/<course_name>', methods=['DELETE'])
@login_required
def api_delete_profile(course_name):
    """Delete a course profile (cannot delete last one)."""
    success = delete_profile(session['user_id'], course_name)
    if not success:
        return jsonify({'error': 'Cannot delete last profile'}), 400
    return jsonify({'success': True})


@profile.route('/api/profile/templates', methods=['GET'])
@login_required
def api_profile_templates():
    """List available profile templates."""
    return jsonify(get_profile_templates())


@profile.route('/api/profile/from-template', methods=['POST'])
@login_required
def api_create_from_template():
    """Create a new profile from a template."""
    data = request.json or {}
    template_id = data.get('template')
    course_name = data.get('course_name')
    if not template_id or not course_name:
        return jsonify({'error': 'template and course_name required'}), 400
    success = create_from_template(session['user_id'], template_id, course_name)
    return jsonify({'success': success})


@profile.route('/api/climate-data/<state>')
@login_required
def api_climate_data(state):
    """Return climate normals for a US state."""
    try:
        from climate_data import get_climate_data
        data = get_climate_data(state)
        if data:
            return jsonify(data)
        return jsonify({'error': 'State not found'}), 404
    except ImportError:
        return jsonify({'error': 'Climate data module not available'}), 500


@profile.route('/api/gdd/<state>')
@login_required
def api_gdd(state):
    """Return current season and GDD info for a state."""
    try:
        from climate_data import get_current_season, get_climate_data
        season = get_current_season(state)
        climate = get_climate_data(state)
        return jsonify({
            'season': season,
            'climate': climate,
        })
    except ImportError:
        return jsonify({'error': 'Climate data module not available'}), 500
