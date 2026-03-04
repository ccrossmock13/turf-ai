"""Course Map API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

course_map_bp = Blueprint("course_map_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@course_map_bp.route("/course-map")
def course_map_page():
    return render_template("course-map.html")


# ====================================================================
# Course Map API
# ====================================================================


@course_map_bp.route("/api/map/zones", methods=["GET"])
def get_map_zones():
    user_id = _user_id()
    zone_type = request.args.get("type")
    try:
        from course_map import get_zones as _get_map_zones

        zones = _get_map_zones(user_id, zone_type=zone_type)
        return jsonify(zones)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map zones: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/zones", methods=["POST"])
def create_map_zone():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import create_zone as _create_map_zone

        zone = _create_map_zone(user_id, data)
        return jsonify(zone), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating map zone: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/zones/<int:zone_id>", methods=["GET"])
def get_map_zone_by_id(zone_id):
    user_id = _user_id()
    try:
        from course_map import get_zone_by_id as _get_zone

        zone = _get_zone(zone_id, user_id)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map zone {zone_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/zones/<int:zone_id>", methods=["PUT"])
def update_map_zone(zone_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import update_zone as _update_map_zone

        zone = _update_map_zone(zone_id, user_id, data)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating map zone {zone_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/zones/<int:zone_id>", methods=["DELETE"])
def delete_map_zone(zone_id):
    user_id = _user_id()
    try:
        from course_map import delete_zone as _delete_map_zone

        result = _delete_map_zone(zone_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting map zone {zone_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/zones/geojson", methods=["GET"])
def get_zones_geojson():
    user_id = _user_id()
    try:
        from course_map import get_zones_geojson as _get_geojson

        geojson = _get_geojson(user_id)
        return jsonify(geojson)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting zones GeoJSON: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/pins", methods=["GET"])
def get_map_pins():
    user_id = _user_id()
    pin_type = request.args.get("type")
    zone_id = request.args.get("zone_id", type=int)
    status = request.args.get("status")
    try:
        from course_map import get_pins as _get_pins

        pins = _get_pins(user_id, pin_type=pin_type, zone_id=zone_id, status=status)
        return jsonify(pins)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map pins: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/pins", methods=["POST"])
def create_map_pin():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import create_pin as _create_pin

        pin = _create_pin(user_id, data)
        return jsonify(pin), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating map pin: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/pins/<int:pin_id>", methods=["PUT"])
def update_map_pin(pin_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import update_pin as _update_pin

        pin = _update_pin(pin_id, user_id, data)
        return jsonify(pin)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating map pin {pin_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/pins/<int:pin_id>", methods=["DELETE"])
def delete_map_pin(pin_id):
    user_id = _user_id()
    try:
        from course_map import delete_pin as _delete_pin

        result = _delete_pin(pin_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting map pin {pin_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/pins/geojson", methods=["GET"])
def get_pins_geojson():
    user_id = _user_id()
    pin_type = request.args.get("type")
    try:
        from course_map import get_pins_geojson as _get_pins_geo

        geojson = _get_pins_geo(user_id, pin_type=pin_type)
        return jsonify(geojson)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting pins GeoJSON: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/layers", methods=["GET"])
def get_map_layers():
    user_id = _user_id()
    try:
        from course_map import get_layers as _get_layers

        layers = _get_layers(user_id)
        return jsonify(layers)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting map layers: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/layers", methods=["POST"])
def create_map_layer():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import create_layer as _create_layer

        layer = _create_layer(user_id, data)
        return jsonify(layer), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating map layer: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/layers/<int:layer_id>", methods=["PUT"])
def update_map_layer(layer_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from course_map import update_layer as _update_layer

        layer = _update_layer(layer_id, user_id, data)
        return jsonify(layer)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating map layer {layer_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/layers/<int:layer_id>", methods=["DELETE"])
def delete_map_layer(layer_id):
    user_id = _user_id()
    try:
        from course_map import delete_layer as _delete_layer

        result = _delete_layer(layer_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting map layer {layer_id}: {e}")
        return jsonify({"error": str(e)}), 500


@course_map_bp.route("/api/map/layers/<path:layer_name>", methods=["GET"])
def get_map_layer_by_name(layer_name):
    user_id = _user_id()
    try:
        from course_map import get_layer_by_name as _get_layer

        layer = _get_layer(user_id, layer_name)
        return jsonify(layer)
    except Exception as e:
        logger.error(f"Error getting map layer {layer_name}: {e}")
        return jsonify({"error": str(e)}), 500
