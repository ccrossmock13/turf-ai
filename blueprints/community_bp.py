"""Community API blueprint."""

import logging

from flask import Blueprint, jsonify, render_template, request

from blueprints.helpers import _check_error, _user_id

logger = logging.getLogger(__name__)

community_bp = Blueprint("community_bp", __name__)


# ====================================================================
# Page Route
# ====================================================================


@community_bp.route("/community")
def community_page():
    return render_template("community.html")


# ====================================================================
# Community API
# ====================================================================


@community_bp.route("/api/community/posts", methods=["GET"])
def get_community_posts():
    category = request.args.get("category")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    try:
        from community import get_posts as _get_posts

        posts = _get_posts(category=category, page=page, per_page=per_page)
        return jsonify(posts)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community posts: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/posts", methods=["POST"])
def create_community_post():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import create_post as _create_post

        result = _create_post(user_id, data)
        if isinstance(result, int):
            from community import get_post_by_id as _get_post

            post = _get_post(result)
        else:
            post = result
        return jsonify(post), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating community post: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/posts/<int:post_id>", methods=["GET"])
def get_community_post_by_id(post_id):
    try:
        from community import get_post_by_id as _get_post

        post = _get_post(post_id)
        return jsonify(post)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community post {post_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/posts/<int:post_id>/replies", methods=["POST"])
@community_bp.route("/api/community/posts/<int:post_id>/reply", methods=["POST"])
def reply_to_community_post(post_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    content = data.get("content", "")
    try:
        from community import create_reply as _create_reply

        result = _create_reply(post_id, user_id, content)
        reply = {"id": result, "post_id": post_id, "content": content} if isinstance(result, int) else result
        return jsonify(reply), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error replying to community post {post_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/posts/<int:post_id>/vote", methods=["POST"])
@community_bp.route("/api/community/posts/<int:post_id>/upvote", methods=["POST"])
def upvote_community_post(post_id):
    user_id = _user_id()
    try:
        from community import upvote_post as _upvote

        result = _upvote(post_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error upvoting community post {post_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/posts/<int:post_id>", methods=["DELETE"])
def delete_community_post(post_id):
    user_id = _user_id()
    try:
        from community import delete_post as _delete_post

        result = _check_error(_delete_post(post_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting community post {post_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/alerts", methods=["GET"])
def get_community_alerts():
    region = request.args.get("region")
    state = request.args.get("state")
    alert_type = request.args.get("type")
    active_only = request.args.get("active_only", "true").lower() == "true"
    try:
        from community import get_alerts as _get_alerts

        alerts = _get_alerts(region=region, state=state, alert_type=alert_type, active_only=active_only)
        return jsonify(alerts)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community alerts: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/alerts", methods=["POST"])
def create_community_alert():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import create_alert as _create_alert

        result = _create_alert(user_id, data)
        alert = {"id": result} if isinstance(result, int) else result
        return jsonify(alert), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating community alert: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/alerts/<int:alert_id>", methods=["DELETE"])
def delete_community_alert(alert_id):
    user_id = _user_id()
    try:
        from community import delete_alert as _delete_alert

        result = _check_error(_delete_alert(alert_id, user_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting community alert {alert_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/alerts/<int:alert_id>/verify", methods=["POST"])
@community_bp.route("/api/community/alerts/<int:alert_id>/vote", methods=["POST"])
def vote_community_alert(alert_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    vote_type = data.get("vote_type", "")
    try:
        from community import vote_alert as _vote_alert

        result = _vote_alert(alert_id, user_id, vote_type)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error voting on community alert {alert_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/programs", methods=["GET"])
def get_community_programs():
    program_type = request.args.get("program_type")
    region = request.args.get("region")
    grass_type = request.args.get("grass_type")
    try:
        from community import get_shared_programs as _get_programs

        programs = _get_programs(program_type=program_type, region=region, grass_type=grass_type)
        return jsonify(programs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community programs: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/programs", methods=["POST"])
def create_community_program():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import share_program as _share_program

        result = _share_program(user_id, data)
        program = {"id": result} if isinstance(result, int) else result
        return jsonify(program), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating community program: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/programs/<int:program_id>/rate", methods=["POST"])
def rate_community_program(program_id):
    user_id = _user_id()
    data = request.get_json(force=True)
    rating = data.get("rating")
    comment = data.get("comment")
    try:
        from community import rate_program as _rate_program

        result = _rate_program(program_id, user_id, rating, comment=comment)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error rating community program {program_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/programs/<int:program_id>/download", methods=["GET"])
def download_community_program(program_id):
    user_id = _user_id()
    try:
        from community import download_program as _download

        result = _download(program_id, user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error downloading community program {program_id}: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/benchmarks", methods=["GET"])
def get_community_benchmarks():
    region = request.args.get("region")
    grass_type = request.args.get("grass_type")
    course_type = request.args.get("course_type")
    try:
        from community import get_benchmarks as _get_benchmarks

        benchmarks = _get_benchmarks(region=region, grass_type=grass_type, course_type=course_type)
        return jsonify(benchmarks)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting community benchmarks: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/benchmarks", methods=["POST"])
def submit_community_benchmark():
    user_id = _user_id()
    data = request.get_json(force=True)
    try:
        from community import submit_benchmark as _submit_bench

        result = _submit_bench(user_id, data)
        benchmark = {"id": result} if isinstance(result, int) else result
        return jsonify(benchmark), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error submitting community benchmark: {e}")
        return jsonify({"error": str(e)}), 500


@community_bp.route("/api/community/benchmarks/compare", methods=["GET"])
def compare_community_benchmarks():
    user_id = _user_id()
    metric_type = request.args.get("metric_type")
    year = request.args.get("year", type=int)
    try:
        from community import get_my_vs_peers as _compare

        comparison = _compare(user_id, metric_type, year=year)
        return jsonify(comparison)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error comparing community benchmarks: {e}")
        return jsonify({"error": str(e)}), 500
