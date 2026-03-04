"""Swagger/OpenAPI configuration for Greenside AI API."""

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: rule.rule.startswith("/api/"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}

SWAGGER_TEMPLATE = {
    "info": {
        "title": "Greenside AI API",
        "description": (
            "RESTful API for the Greenside AI turfgrass management platform. "
            "Provides endpoints for equipment tracking, irrigation management, "
            "crew scheduling, budget tracking, spray records, scouting reports, "
            "soil testing, and more."
        ),
        "version": "1.0.0",
        "contact": {
            "name": "Greenside AI",
        },
    },
    "securityDefinitions": {
        "SessionAuth": {
            "type": "apiKey",
            "name": "session",
            "in": "cookie",
            "description": "Session-based authentication. Login via POST /api/login first.",
        }
    },
    "security": [{"SessionAuth": []}],
    "tags": [
        {"name": "Auth", "description": "Authentication and user management"},
        {"name": "Profile", "description": "Course profile management"},
        {"name": "Equipment", "description": "Equipment inventory and maintenance"},
        {"name": "Irrigation", "description": "Irrigation zone and water management"},
        {"name": "Crew", "description": "Crew scheduling and time tracking"},
        {"name": "Budget", "description": "Budget and expense tracking"},
        {"name": "Spray", "description": "Spray application records and compliance"},
        {"name": "Calendar", "description": "Maintenance calendar and scheduling"},
        {"name": "Scouting", "description": "Field scouting reports"},
        {"name": "Soil", "description": "Soil testing and amendments"},
        {"name": "Community", "description": "Community forum and programs"},
        {"name": "Cultivar", "description": "NTEP cultivar data and recommendations"},
        {"name": "Reports", "description": "Report generation and export"},
        {"name": "Organizations", "description": "Multi-tenant organization management"},
        {"name": "Intelligence", "description": "AI intelligence engine"},
    ],
}
