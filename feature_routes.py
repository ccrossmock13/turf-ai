"""
Feature Routes — Greenside AI Turfgrass Management App.

Routes have been extracted to individual blueprint files in blueprints/.
This module retains:
  - init_all_feature_tables() for database initialization
  - features_bp with the /dashboard page route (backward compatibility)
"""

from flask import Blueprint, render_template
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


# ---------------------------------------------------------------------------
# Dashboard page route (kept here for backward compatibility)
# ---------------------------------------------------------------------------

@features_bp.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')
