"""Calculator / Unit Converter API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

logger = logging.getLogger(__name__)

calculator_bp = Blueprint("calculator_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@calculator_bp.route("/calculator")
def calculator_page():
    return render_template("calculator.html")


# ====================================================================
# Calculator API
# ====================================================================


@calculator_bp.route("/api/calculator/convert-rate", methods=["POST"])
def convert_rate():
    data = request.get_json(force=True)
    value = data.get("value")
    from_rate = data.get("from_rate")
    to_rate = data.get("to_rate")
    try:
        from unit_converter import convert_rate as _convert

        result = _convert(value, from_rate, to_rate)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error converting rate: {e}")
        return jsonify({"error": str(e)}), 500


@calculator_bp.route("/api/calculator/spray", methods=["POST"])
def calculate_spray():
    data = request.get_json(force=True)
    speed_mph = data.get("speed_mph")
    nozzle_spacing_inches = data.get("nozzle_spacing_inches")
    flow_rate_gpm = data.get("flow_rate_gpm")
    try:
        from unit_converter import calculate_gpa as _calc_gpa

        result = _calc_gpa(speed_mph, nozzle_spacing_inches, flow_rate_gpm)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error calculating spray: {e}")
        return jsonify({"error": str(e)}), 500


@calculator_bp.route("/api/calculator/fertilizer", methods=["POST"])
def calculate_fertilizer():
    data = request.get_json(force=True)
    target_n_rate = data.get("target_n_rate")
    npk_analysis = data.get("npk_analysis")
    area_sqft = data.get("area_sqft", 1000)
    try:
        from unit_converter import calculate_product_rate_for_target_n as _calc_fert

        result = _calc_fert(target_n_rate, npk_analysis, area_sqft=area_sqft)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error calculating fertilizer: {e}")
        return jsonify({"error": str(e)}), 500


@calculator_bp.route("/api/calculator/gdd", methods=["POST"])
def calculate_gdd():
    data = request.get_json(force=True)
    tmax = data.get("tmax")
    tmin = data.get("tmin")
    base = data.get("base", 50)
    cap = data.get("cap", 86)
    try:
        from unit_converter import calculate_gdd as _calc_gdd

        result = _calc_gdd(tmax, tmin, base=base, cap=cap)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error calculating GDD: {e}")
        return jsonify({"error": str(e)}), 500
