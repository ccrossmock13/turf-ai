"""Soil Testing API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

soil_bp = Blueprint("soil_bp", __name__)


# ====================================================================
# Soil field mappings (only used by soil routes)
# ====================================================================

_SOIL_FIELD_MAP = {
    "date": "test_date",
    "lab": "lab_name",
    "om_pct": "organic_matter",
    "p_ppm": "phosphorus_ppm",
    "k_ppm": "potassium_ppm",
    "ca_ppm": "calcium_ppm",
    "mg_ppm": "magnesium_ppm",
    "s_ppm": "sulfur_ppm",
    "fe_ppm": "iron_ppm",
    "mn_ppm": "manganese_ppm",
    "zn_ppm": "zinc_ppm",
    "cu_ppm": "copper_ppm",
    "b_ppm": "boron_ppm",
    "na_ppm": "sodium_ppm",
    "no3_ppm": "nitrate_ppm",
    "ca_sat": "base_saturation_ca",
    "mg_sat": "base_saturation_mg",
    "k_sat": "base_saturation_k",
    "na_sat": "base_saturation_na",
    "h_sat": "base_saturation_h",
}
_SOIL_FIELD_MAP_REV = {v: k for k, v in _SOIL_FIELD_MAP.items()}


_WATER_FIELD_MAP = {
    "date": "test_date",
    "tds": "tds_ppm",
    "hardness": "hardness_ppm",
    "alkalinity": "bicarbonate_ppm",
    "na_ppm": "sodium_ppm",
    "ca_ppm": "calcium_ppm",
    "mg_ppm": "magnesium_ppm",
    "cl_ppm": "chloride_ppm",
    "hco3_ppm": "bicarbonate_ppm",
    "fe_ppm": "iron_ppm",
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
# Page Route
# ====================================================================


@soil_bp.route("/soil")
def soil_page():
    return render_template("soil.html")


# ====================================================================
# Soil API
# ====================================================================


@soil_bp.route("/api/soil/tests", methods=["GET"])
def get_soil_tests():
    user_id = _user_id()
    area = request.args.get("area")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        from soil_testing import get_soil_tests as _get_soil

        tests = _get_soil(user_id, area=area, start_date=start_date, end_date=end_date)
        return jsonify([_soil_outbound(t) for t in tests])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil tests: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/tests", methods=["POST"])
def create_soil_test():
    user_id = _user_id()
    data = _soil_inbound(request.get_json(force=True))
    try:
        from soil_testing import add_soil_test as _add_soil

        result = _add_soil(user_id, data)
        if result is None:
            return jsonify({"error": "Failed to create soil test. Check required fields: test_date, area, ph"}), 400
        # add_soil_test returns bare int ID - fetch full record
        from soil_testing import get_soil_test_by_id as _get_soil_by_id

        test = _get_soil_by_id(result, user_id)
        return jsonify(_soil_outbound(test)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating soil test: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/tests/<int:test_id>", methods=["GET"])
def get_soil_test_by_id(test_id):
    user_id = _user_id()
    try:
        from soil_testing import get_soil_test_by_id as _get_soil_by_id

        test = _get_soil_by_id(test_id, user_id)
        return jsonify(_soil_outbound(test))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil test {test_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/tests/<int:test_id>", methods=["PUT"])
def update_soil_test(test_id):
    user_id = _user_id()
    data = _soil_inbound(request.get_json(force=True))
    try:
        from soil_testing import update_soil_test as _update_soil

        test = _update_soil(test_id, user_id, data)
        return jsonify(_soil_outbound(test))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating soil test {test_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/tests/<int:test_id>", methods=["DELETE"])
def delete_soil_test(test_id):
    user_id = _user_id()
    try:
        from soil_testing import delete_soil_test as _delete_soil

        result = _delete_soil(test_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting soil test {test_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/tests/<int:test_id>/amendments", methods=["GET"])
def get_soil_amendments(test_id):
    user_id = _user_id()
    try:
        from soil_testing import get_amendments as _get_amend

        amendments = _get_amend(test_id, user_id)
        return jsonify(amendments)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil amendments: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/tests/<int:test_id>/amendments/generate", methods=["POST"])
def generate_amendment_recommendations(test_id):
    user_id = _user_id()
    data = request.get_json(silent=True) or {}
    target_ph = data.get("target_ph")
    try:
        from soil_testing import generate_amendment_recommendations as _gen_amend

        result = _gen_amend(test_id, user_id, target_ph=target_ph)
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating amendment recommendations for test {test_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/amendments", methods=["GET"])
def get_all_amendments():
    user_id = _user_id()
    area = request.args.get("area")
    try:
        from soil_testing import get_all_amendments as _get_amend

        amendments = _get_amend(user_id, area=area)
        return jsonify(amendments)
    except Exception as e:
        logger.error(f"Error getting amendments: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/amendments/<int:amendment_id>/apply", methods=["POST"])
def apply_amendment(amendment_id):
    user_id = _user_id()
    try:
        from soil_testing import apply_amendment as _apply_amend

        result = _apply_amend(amendment_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error applying amendment {amendment_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/water-tests", methods=["GET"])
def get_water_tests():
    user_id = _user_id()
    try:
        from soil_testing import get_water_tests as _get_water

        tests = _get_water(user_id)
        return jsonify(tests)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water tests: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/water-tests", methods=["POST"])
def create_water_test():
    user_id = _user_id()
    data = _water_inbound(request.get_json(force=True))
    try:
        from soil_testing import add_water_test as _add_water

        result = _add_water(user_id, data)
        if result is None:
            return jsonify({"error": "Failed to create water test. Check required field: test_date"}), 400
        from soil_testing import get_water_test_by_id as _get_wt

        test = _get_wt(result, user_id)
        return jsonify(test), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating water test: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/water-tests/<int:test_id>/assessment", methods=["GET"])
def get_water_quality_assessment(test_id):
    user_id = _user_id()
    try:
        from soil_testing import get_water_quality_assessment as _get_wqa

        assessment = _get_wqa(test_id, user_id)
        return jsonify(assessment)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting water quality assessment {test_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/water-tests/<int:test_id>", methods=["DELETE"])
def delete_water_test(test_id):
    user_id = _user_id()
    try:
        from soil_testing import delete_water_test as _del_water

        result = _del_water(test_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting water test {test_id}: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/trends", methods=["GET"])
def get_soil_trends():
    user_id = _user_id()
    area = request.args.get("area")
    parameter = request.args.get("parameter")
    years = request.args.get("years", 5, type=int)
    try:
        from soil_testing import get_soil_trend as _get_trend

        trends = _get_trend(user_id, area, parameter, years=years)
        return jsonify(trends)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting soil trends: {e}")
        return jsonify({"error": str(e)}), 500


@soil_bp.route("/api/soil/optimal-ranges", methods=["GET"])
def get_optimal_ranges():
    grass_type = request.args.get("grass_type")
    area = request.args.get("area")
    try:
        from soil_testing import get_optimal_ranges as _get_ranges

        ranges = _get_ranges(grass_type, area)
        return jsonify(ranges)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting optimal ranges: {e}")
        return jsonify({"error": str(e)}), 500
