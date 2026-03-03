"""Cultivar API blueprint."""

from flask import Blueprint, jsonify, request, render_template
import logging

from blueprints.helpers import _user_id

logger = logging.getLogger(__name__)

cultivar_bp = Blueprint('cultivar_bp', __name__)


# ====================================================================
# Page Route
# ====================================================================

@cultivar_bp.route('/cultivars')
def cultivars_page():
    return render_template('cultivars.html')


# ====================================================================
# Cultivar API
# ====================================================================

@cultivar_bp.route('/api/cultivars/search', methods=['GET'])
def search_cultivars():
    species = request.args.get('species')
    category = request.args.get('category')
    region = request.args.get('region')
    min_quality = request.args.get('min_quality', type=float)
    try:
        from cultivar_tool import search_cultivars as _search
        results = _search(species=species, category=category, region=region, min_quality=min_quality)
        return jsonify(results)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error searching cultivars: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/compare', methods=['POST'])
def compare_cultivars():
    data = request.get_json(force=True)
    cultivar_names = data.get('cultivar_names', [])
    criteria_weights = data.get('criteria_weights')
    try:
        from cultivar_tool import compare_cultivars as _compare
        comparison = _compare(cultivar_names, criteria_weights=criteria_weights)
        return jsonify(comparison)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error comparing cultivars: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/recommend', methods=['POST'])
def recommend_cultivars():
    data = request.get_json(force=True)
    try:
        from cultivar_tool import recommend_cultivars as _recommend
        recommendations = _recommend(data)
        return jsonify(recommendations)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting cultivar recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/renovation', methods=['GET'])
def get_renovation_plans():
    user_id = _user_id()
    try:
        from cultivar_tool import get_renovation_projects as _get_projects
        plans = _get_projects(user_id)
        return jsonify(plans)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting renovation plans: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/renovation', methods=['POST'])
def create_renovation_plan():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from cultivar_tool import create_renovation_project as _create_project
        plan = _create_project(user_id, data)
        return jsonify(plan), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating renovation plan: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/renovation/<int:plan_id>', methods=['PUT'])
def update_renovation_plan(plan_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from cultivar_tool import update_renovation_project as _update_project
        plan = _update_project(plan_id, user_id, data)
        return jsonify(plan)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating renovation plan {plan_id}: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/renovation/<int:plan_id>', methods=['DELETE'])
def delete_renovation_project(plan_id):
    user_id = _user_id()
    try:
        from cultivar_tool import delete_renovation_project as _del_reno
        result = _del_reno(plan_id, user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting renovation project {plan_id}: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/blend', methods=['GET'])
def get_cultivar_blend():
    species = request.args.get('species')
    category = request.args.get('category')
    region = request.args.get('region')
    try:
        from cultivar_tool import get_blend_recommendation as _get_blend
        blend = _get_blend(species, category=category, region=region)
        return jsonify(blend)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting cultivar blend: {e}")
        return jsonify({'error': str(e)}), 500


@cultivar_bp.route('/api/cultivars/seeding-rate', methods=['GET'])
def get_seeding_rate():
    cultivar_name = request.args.get('cultivar')
    method = request.args.get('method', 'seed')
    area_sqft = request.args.get('area_sqft', 1000.0, type=float)
    try:
        from cultivar_tool import calculate_seeding_rate as _calc_rate
        rate = _calc_rate(cultivar_name, method=method, area_sqft=area_sqft)
        return jsonify(rate)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting seeding rate: {e}")
        return jsonify({'error': str(e)}), 500
