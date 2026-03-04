"""Irrigation API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

irrigation_bp = Blueprint("irrigation_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@irrigation_bp.route("/irrigation")
def irrigation_page():
    return render_template("irrigation.html")


# ====================================================================
# Irrigation API
# ====================================================================


@irrigation_bp.route("/api/irrigation/zones", methods=["GET"])
def get_irrigation_zones():
    user_id = _user_id()
    area = request.args.get("area")
    try:
        from irrigation_manager import get_zones as _get_zones

        zones = _get_zones(user_id, area=area)
        return jsonify(zones)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation zones: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/zones", methods=["POST"])
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
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating irrigation zone: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/zones/<int:zone_id>", methods=["GET"])
def get_irrigation_zone_by_id(zone_id):
    user_id = _user_id()
    try:
        from irrigation_manager import get_zone_by_id as _get_zone

        zone = _get_zone(zone_id, user_id)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation zone {zone_id}: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/zones/<int:zone_id>", methods=["PUT"])
def update_irrigation_zone(zone_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import update_zone as _update_zone

        zone = _update_zone(zone_id, user_id, data)
        return jsonify(zone)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating irrigation zone {zone_id}: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/zones/<int:zone_id>", methods=["DELETE"])
def delete_irrigation_zone(zone_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_zone as _delete_zone

        result = _delete_zone(zone_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting irrigation zone {zone_id}: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/runs", methods=["GET"])
def get_irrigation_runs():
    user_id = _user_id()
    zone_id = request.args.get("zone_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from irrigation_manager import get_irrigation_history as _get_history

        runs = _get_history(user_id, zone_id=zone_id, start_date=start_date, end_date=end_date)
        return jsonify(runs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation runs: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/runs", methods=["POST"])
def create_irrigation_run():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_irrigation_run as _log_run

        result = _log_run(user_id, data)
        run = {"id": result} if isinstance(result, int) else result
        return jsonify(run), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating irrigation run: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/runs/<int:run_id>", methods=["DELETE"])
def delete_irrigation_run(run_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_irrigation_run as _del_run

        result = _del_run(run_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting irrigation run {run_id}: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/moisture", methods=["GET"])
def get_moisture_readings():
    user_id = _user_id()
    zone_id = request.args.get("zone_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from irrigation_manager import get_moisture_readings as _get_moisture

        readings = _get_moisture(user_id, zone_id=zone_id, start_date=start_date, end_date=end_date)
        return jsonify(readings)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting moisture readings: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/moisture", methods=["POST"])
def create_moisture_reading():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_moisture_reading as _log_moisture

        result = _log_moisture(user_id, data)
        reading = {"id": result} if isinstance(result, int) else result
        return jsonify(reading), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating moisture reading: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/moisture/<int:reading_id>", methods=["DELETE"])
def delete_moisture_reading(reading_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_moisture_reading as _del_moisture

        result = _del_moisture(reading_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting moisture reading {reading_id}: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/et", methods=["POST"])
def create_et_entry():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_et_data as _log_et

        result = _log_et(user_id, data)
        entry = {"id": result} if isinstance(result, int) else result
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating ET entry: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/et", methods=["GET"])
def get_et_data():
    user_id = _user_id()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from irrigation_manager import get_et_data as _get_et

        data = _get_et(user_id, start_date=start_date, end_date=end_date)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting ET data: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/water-usage", methods=["GET"])
def get_water_usage():
    user_id = _user_id()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from irrigation_manager import get_water_usage as _get_usage

        usage = _get_usage(user_id, start_date=start_date, end_date=end_date)
        return jsonify(usage)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water usage: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/water-usage", methods=["POST"])
def log_water_usage():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from irrigation_manager import log_water_usage as _log_usage

        result = _log_usage(user_id, data)
        usage = {"id": result} if isinstance(result, int) else result
        return jsonify(usage), 201
    except Exception as e:
        logger.error(f"Error logging water usage: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/water-usage/<int:usage_id>", methods=["DELETE"])
def delete_water_usage(usage_id):
    user_id = _user_id()
    try:
        from irrigation_manager import delete_water_usage as _del_usage

        result = _del_usage(usage_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting water usage {usage_id}: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/recommendations", methods=["GET"])
def get_irrigation_recommendations():
    user_id = _user_id()
    zone_id = request.args.get("zone_id", type=int)
    try:
        from irrigation_manager import get_irrigation_recommendation as _get_rec

        recs = _get_rec(user_id, zone_id=zone_id)
        return jsonify(recs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting irrigation recommendations: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/water-balance", methods=["GET"])
def get_water_balance():
    user_id = _user_id()
    zone_id = request.args.get("zone_id", type=int)
    days = request.args.get("days", 14, type=int)
    try:
        from irrigation_manager import get_water_balance as _get_balance

        balance = _get_balance(user_id, zone_id, days=days)
        return jsonify(balance)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water balance: {e}")
        return jsonify({"error": str(e)}), 500


@irrigation_bp.route("/api/irrigation/drought-status", methods=["GET"])
def get_drought_status():
    user_id = _user_id()
    try:
        from irrigation_manager import get_drought_status as _get_drought

        status = _get_drought(user_id)
        return jsonify(status)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting drought status: {e}")
        return jsonify({"error": str(e)}), 500
