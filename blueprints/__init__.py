"""Blueprint registration for Greenside AI."""

import logging

logger = logging.getLogger(__name__)


def register_blueprints(app):
    """Register all application blueprints with the Flask app."""

    from blueprints.auth_bp import auth
    from blueprints.profile_bp import profile
    from blueprints.spray_bp import spray
    from blueprints.chat_bp import chat_bp
    from blueprints.admin_bp import admin_bp
    from blueprints.intelligence_bp import intelligence_bp

    from blueprints.calendar_bp import calendar_bp
    from blueprints.budget_bp import budget_bp
    from blueprints.scouting_bp import scouting_bp
    from blueprints.crew_bp import crew_bp
    from blueprints.equipment_bp import equipment_bp
    from blueprints.irrigation_bp import irrigation_bp
    from blueprints.soil_bp import soil_bp
    from blueprints.community_bp import community_bp
    from blueprints.cultivar_bp import cultivar_bp
    from blueprints.notifications_bp import notifications_bp
    from blueprints.reporting_bp import reporting_bp
    from blueprints.calculator_bp import calculator_bp
    from blueprints.course_map_bp import course_map_bp
    from blueprints.org_bp import org_bp

    # App-level blueprints (extracted from app.py)
    app.register_blueprint(auth)
    app.register_blueprint(profile)
    app.register_blueprint(spray)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(intelligence_bp)

    # Feature module blueprints (extracted from feature_routes.py)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(scouting_bp)
    app.register_blueprint(crew_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(irrigation_bp)
    app.register_blueprint(soil_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(cultivar_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(calculator_bp)
    app.register_blueprint(course_map_bp)

    # Organization management (multi-tenancy)
    app.register_blueprint(org_bp)

    # Initialize organization tables
    try:
        from blueprints.org_context import init_org_tables
        init_org_tables()
    except Exception as e:
        logger.warning(f"Org table init: {e}")

    logger.info("All blueprints registered")
