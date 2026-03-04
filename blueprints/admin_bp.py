"""
Admin blueprint.

Extracted from app.py — contains all /admin/* routes:
  - /admin (dashboard)
  - /admin/stats, /admin/cache, /admin/feedback/*, /admin/review-queue
  - /admin/moderate, /admin/promote-to-golden, /admin/moderator-history
  - /admin/training/generate, /admin/knowledge, /admin/knowledge/build
  - /admin/bulk-moderate, /admin/bulk-approve-high-confidence
  - /admin/export/feedback, /admin/export/training, /admin/export/moderation, /admin/export/analytics
  - /admin/priority-queue, /admin/trending-issues, /admin/question-frequencies
  - /admin/fine-tuning/status, /admin/fine-tuning/start, /admin/fine-tuning/job/<id>
  - /admin/source-quality
  - /admin/eval/run, /admin/eval/history
"""

import os

from flask import Blueprint, jsonify, render_template, request

from logging_config import logger

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# Lazy accessor for singleton clients created in app.py
# ---------------------------------------------------------------------------


def _get_clients():
    """Lazy import of singleton clients from app module."""
    import app as _app

    return _app.openai_client, _app.index


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------


@admin_bp.route("/admin")
def admin_dashboard():
    return render_template("admin.html")


@admin_bp.route("/admin/stats")
def admin_stats():
    from feedback_system import get_feedback_stats

    return jsonify(get_feedback_stats())


@admin_bp.route("/admin/cache")
def admin_cache_stats():
    """Get cache statistics for monitoring."""
    from cache import get_embedding_cache, get_search_cache, get_source_url_cache

    return jsonify(
        {
            "embedding_cache": get_embedding_cache().stats(),
            "source_url_cache": get_source_url_cache().stats(),
            "search_cache": get_search_cache().stats(),
        }
    )


# ---------------------------------------------------------------------------
# Feedback review
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/feedback/review")
def admin_feedback_review():
    from feedback_system import get_negative_feedback

    return jsonify(get_negative_feedback(limit=100, unreviewed_only=True))


@admin_bp.route("/admin/feedback/needs-review")
def admin_needs_review():
    """Get queries that were auto-flagged for human review (< 70% confidence)"""
    from feedback_system import get_queries_needing_review

    return jsonify(get_queries_needing_review(limit=100))


@admin_bp.route("/admin/feedback/all")
def admin_feedback_all():
    from db import FEEDBACK_DB, get_db

    with get_db(FEEDBACK_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question, ai_answer, user_rating, user_correction, timestamp, confidence_score
            FROM feedback ORDER BY timestamp DESC LIMIT 100
        """)
        results = cursor.fetchall()

    feedback = [
        {
            "id": row[0],
            "question": row[1],
            "ai_answer": row[2],
            "rating": row[3],
            "correction": row[4],
            "timestamp": row[5],
            "confidence": row[6],
        }
        for row in results
    ]
    return jsonify(feedback)


@admin_bp.route("/admin/feedback/approve", methods=["POST"])
def admin_approve_feedback():
    from feedback_system import approve_for_training

    data = request.json
    approve_for_training(data.get("id"), data.get("correction"))
    return jsonify({"success": True})


@admin_bp.route("/admin/feedback/reject", methods=["POST"])
def admin_reject_feedback():
    from feedback_system import reject_feedback

    data = request.json
    reject_feedback(data.get("id"), "Rejected by admin")
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/review-queue")
def admin_review_queue():
    """Get unified moderation queue (user-flagged + auto-flagged)"""
    from feedback_system import get_review_queue

    queue_type = request.args.get("type", "all")  # all, negative, low_confidence
    return jsonify(get_review_queue(limit=100, queue_type=queue_type))


@admin_bp.route("/admin/moderate", methods=["POST"])
def admin_moderate():
    """Moderate an answer: approve, reject, or correct"""
    from feedback_system import moderate_answer

    data = request.json
    result = moderate_answer(
        feedback_id=data.get("id"),
        action=data.get("action"),  # approve, reject, correct
        corrected_answer=data.get("corrected_answer"),
        reason=data.get("reason"),
        moderator=data.get("moderator", "admin"),
    )
    return jsonify(result)


@admin_bp.route("/admin/promote-to-golden", methods=["POST"])
def admin_promote_to_golden():
    """Promote a moderation queue item to a golden answer"""
    from intelligence_engine import SelfHealingLoop

    data = request.json
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    category = data.get("category", "").strip() or None
    if not question or not answer:
        return jsonify({"success": False, "error": "Question and answer required"})
    ga_id = SelfHealingLoop.create_golden_answer(question, answer, category)
    return jsonify({"success": True, "id": ga_id})


@admin_bp.route("/admin/moderator-history")
def admin_moderator_history():
    """Get audit trail of moderator actions"""
    from feedback_system import get_moderator_history

    return jsonify(get_moderator_history(limit=100))


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/training/generate", methods=["POST"])
def admin_generate_training():
    """Generate JSONL training file from approved feedback using the fine-tuning pipeline."""
    from fine_tuning import prepare_training_data

    result = prepare_training_data()
    if result.get("success"):
        return jsonify({"success": True, "filepath": result["path"], "num_examples": result["num_examples"]})
    return jsonify(
        {
            "success": False,
            "message": result.get("error", "Not enough approved examples"),
            "current_count": result.get("current_count", 0),
            "needed": result.get("needed", 50),
        }
    )


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/knowledge")
def admin_knowledge_status():
    """Get knowledge base status including PDFs and web-scraped content."""
    _openai_client, index = _get_clients()
    try:
        from knowledge_builder import IndexTracker, scan_for_pdfs
    except ImportError as ie:
        logger.warning(f"knowledge_builder unavailable: {ie}")
        return jsonify(
            {
                "indexed_files": 0,
                "total_chunks": 0,
                "last_run": None,
                "total_pdfs": 0,
                "unindexed": 0,
                "unindexed_sample": [],
                "pinecone_total_vectors": 0,
                "scraped_sources": {},
                "warning": f"Knowledge builder unavailable: {ie}",
            }
        )

    tracker = IndexTracker()
    stats = tracker.get_stats()

    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]

    # Get total vectors from Pinecone (includes PDFs + scraped web guides)
    pinecone_vectors = 0
    try:
        pinecone_stats = index.describe_index_stats()
        pinecone_vectors = pinecone_stats.get("total_vector_count", 0)
    except Exception as e:
        logger.warning(f"Could not get Pinecone stats: {e}")

    # Count scraped knowledge sources
    scraped_sources = {
        "disease_guides": {"source": "GreenCast", "type": "disease_guide"},
        "weed_guides": {"source": "GreenCast", "type": "weed_guide"},
        "pest_guides": {"source": "NC State TurfFiles", "type": "pest_guide"},
        "cultural_practices": {"source": "University Extensions", "type": "cultural_practices"},
        "nematode_guides": {"source": "UF/UC/Penn State/NC State", "type": "nematode_guide"},
        "abiotic_disorders": {"source": "University Extensions", "type": "abiotic_disorders"},
        "irrigation": {"source": "University Extensions", "type": "irrigation"},
        "fertility": {"source": "University Extensions", "type": "fertility"},
    }

    return jsonify(
        {
            "indexed_files": stats["total_files"],
            "total_chunks": stats["total_chunks"],
            "last_run": stats["last_run"],
            "total_pdfs": len(all_pdfs),
            "unindexed": len(unindexed),
            "unindexed_sample": [os.path.basename(f) for f in unindexed[:10]],
            "pinecone_total_vectors": pinecone_vectors,
            "scraped_sources": scraped_sources,
        }
    )


@admin_bp.route("/admin/knowledge/build", methods=["POST"])
def admin_knowledge_build():
    """Trigger knowledge base build (limited for safety)."""
    import threading

    from knowledge_builder import IndexTracker, build_knowledge_base, scan_for_pdfs

    data = request.get_json(silent=True) or {}
    limit = data.get("limit", 10)

    # Check if there are actually files to index
    tracker = IndexTracker()
    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]

    if not unindexed:
        return jsonify({"success": True, "message": "All PDF files are already indexed. No new files to process."})

    actual_limit = min(limit, len(unindexed))

    # Run in background thread with status tracking
    build_status = {"running": True, "error": None}

    def run_build():
        try:
            build_knowledge_base(limit=actual_limit)
        except Exception as e:
            logger.error(f"Knowledge build error: {e}")
            build_status["error"] = str(e)
        finally:
            build_status["running"] = False

    thread = threading.Thread(target=run_build, daemon=True)
    thread.start()

    return jsonify(
        {"success": True, "message": f"Indexing {actual_limit} of {len(unindexed)} unindexed PDFs in background"}
    )


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/bulk-moderate", methods=["POST"])
def admin_bulk_moderate():
    """Bulk approve or reject multiple items"""
    from feedback_system import bulk_moderate

    data = request.json
    ids = data.get("ids", [])
    action = data.get("action", "approve")
    reason = data.get("reason")

    if not ids:
        return jsonify({"success": False, "error": "No IDs provided"})

    result = bulk_moderate(ids, action, reason)
    return jsonify(result)


@admin_bp.route("/admin/bulk-approve-high-confidence", methods=["POST"])
def admin_bulk_approve_high_confidence():
    """Auto-approve all high-confidence items"""
    from feedback_system import bulk_approve_high_confidence

    data = request.json or {}
    min_confidence = data.get("min_confidence", 80)
    limit = data.get("limit", 100)

    result = bulk_approve_high_confidence(min_confidence, limit)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Export Routes
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/export/feedback")
def admin_export_feedback():
    """Export all feedback as CSV"""
    from flask import Response

    from feedback_system import export_feedback_csv

    csv_data = export_feedback_csv()
    return Response(
        csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=feedback_export.csv"}
    )


@admin_bp.route("/admin/export/training")
def admin_export_training():
    """Export training examples as CSV"""
    from flask import Response

    from feedback_system import export_training_examples_csv

    csv_data = export_training_examples_csv()
    return Response(
        csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=training_examples.csv"}
    )


@admin_bp.route("/admin/export/moderation")
def admin_export_moderation():
    """Export moderation history as CSV"""
    from flask import Response

    from feedback_system import export_moderation_history_csv

    csv_data = export_moderation_history_csv()
    return Response(
        csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=moderation_history.csv"}
    )


@admin_bp.route("/admin/export/analytics")
def admin_export_analytics():
    """Export analytics data as JSON"""
    from feedback_system import export_analytics_json

    return jsonify(export_analytics_json())


# ---------------------------------------------------------------------------
# Priority Queue Routes
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/priority-queue")
def admin_priority_queue():
    """Get priority-sorted review queue"""
    from feedback_system import get_priority_review_queue

    limit = request.args.get("limit", 100, type=int)
    return jsonify(get_priority_review_queue(limit))


@admin_bp.route("/admin/trending-issues")
def admin_trending_issues():
    """Get trending problem areas"""
    from feedback_system import get_trending_issues

    min_frequency = request.args.get("min_frequency", 3, type=int)
    days = request.args.get("days", 7, type=int)
    return jsonify(get_trending_issues(min_frequency, days))


@admin_bp.route("/admin/question-frequencies")
def admin_question_frequencies():
    """Get frequently asked questions"""
    from feedback_system import get_question_frequencies

    limit = request.args.get("limit", 50, type=int)
    return jsonify(get_question_frequencies(limit))


# ---------------------------------------------------------------------------
# Fine-tuning Routes
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/fine-tuning/status")
def admin_fine_tuning_status():
    """Get fine-tuning status and training data readiness"""
    from feedback_system import get_training_examples
    from fine_tuning import MIN_EXAMPLES_FOR_TRAINING, get_active_fine_tuned_model, list_fine_tuning_jobs

    examples = get_training_examples(unused_only=True)
    jobs = list_fine_tuning_jobs(limit=5)
    active_model = get_active_fine_tuned_model()

    return jsonify(
        {
            "training_examples_ready": len(examples),
            "min_examples_needed": MIN_EXAMPLES_FOR_TRAINING,
            "ready_to_train": len(examples) >= MIN_EXAMPLES_FOR_TRAINING,
            "recent_jobs": jobs,
            "active_fine_tuned_model": active_model,
        }
    )


@admin_bp.route("/admin/fine-tuning/start", methods=["POST"])
def admin_start_fine_tuning():
    """Start the fine-tuning pipeline"""
    from fine_tuning import run_full_fine_tuning_pipeline

    result = run_full_fine_tuning_pipeline()
    return jsonify(result)


@admin_bp.route("/admin/fine-tuning/job/<job_id>")
def admin_fine_tuning_job_status(job_id):
    """Get status of a specific fine-tuning job"""
    from fine_tuning import get_fine_tuning_status

    status = get_fine_tuning_status(job_id)
    return jsonify(status)


@admin_bp.route("/admin/source-quality")
def admin_source_quality():
    """Get source quality scores from feedback"""
    from fine_tuning import get_low_quality_sources, get_source_quality_scores

    return jsonify({"all_scores": get_source_quality_scores(), "low_quality": get_low_quality_sources(threshold=0.4)})


# ---------------------------------------------------------------------------
# Eval Routes
# ---------------------------------------------------------------------------


@admin_bp.route("/admin/eval/run", methods=["POST"])
def admin_run_evaluation():
    """Run evaluation against test questions"""
    from fine_tuning import run_evaluation, save_eval_results

    try:
        # Check if we should use the full 100-question set
        body = request.get_json(silent=True) or {}
        use_full = body.get("full", False)

        if use_full:
            from eval_questions_100 import EVAL_QUESTIONS_100

            results = run_evaluation(custom_questions=EVAL_QUESTIONS_100)
        else:
            results = run_evaluation()

        run_id = save_eval_results(results)
        results["run_id"] = run_id
        return jsonify(results)
    except Exception as e:
        import traceback

        logger.error(f"Evaluation error: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/admin/eval/history")
def admin_eval_history():
    """Get evaluation run history"""
    from fine_tuning import get_eval_history

    limit = request.args.get("limit", 10, type=int)
    return jsonify(get_eval_history(limit))
