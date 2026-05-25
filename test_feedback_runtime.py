import unittest
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import feedback_system


class FeedbackRuntimeTests(unittest.TestCase):
    def test_update_query_rating_uses_exact_feedback_id_when_present(self):
        with tempfile.TemporaryDirectory(prefix="feedback-runtime-") as temp_dir:
            db_path = os.path.join(temp_dir, "feedback.db")
            with patch.object(feedback_system, "DB_PATH", db_path), \
                 patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=False):
                feedback_system.init_feedback_database()
                first_id = feedback_system.save_query("Same question?", "Answer one")
                second_id = feedback_system.save_query("Same question?", "Answer two")

                updated_id = feedback_system.update_query_rating(
                    question="Same question?",
                    rating="negative",
                    correction="Second row only",
                    feedback_id=first_id,
                )

                self.assertEqual(updated_id, first_id)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT id, user_rating, user_correction FROM feedback ORDER BY id ASC")
                rows = cursor.fetchall()
                conn.close()

                self.assertEqual(rows, [
                    (first_id, "negative", "Second row only"),
                    (second_id, "unrated", None),
                ])

    def test_feedback_item_loader_ignores_router_records(self):
        scan_table = Mock()
        scan_table.scan.return_value = {
            "Items": [
                {"id": "1", "item_type": "feedback", "question": "Q1", "timestamp": "2026-04-14T10:00:00"},
                {"id": "2", "item_type": "router_event", "question": "Q2", "created_at": "2026-04-14T11:00:00"},
            ]
        }
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_feedback_table", return_value=scan_table):
            items = feedback_system._load_feedback_items()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "1")

    def test_feedback_item_loader_follows_dynamodb_scan_pagination(self):
        scan_table = Mock()
        scan_table.scan.side_effect = [
            {
                "Items": [
                    {"id": "1", "item_type": "feedback", "question": "Q1", "timestamp": "2026-04-14T10:00:00"},
                ],
                "LastEvaluatedKey": {"id": "1"},
            },
            {
                "Items": [
                    {"id": "2", "item_type": "feedback", "question": "Q2", "timestamp": "2026-04-14T11:00:00"},
                ],
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_feedback_table", return_value=scan_table):
            items = feedback_system._load_feedback_items()

        self.assertEqual([item["id"] for item in items], ["2", "1"])
        self.assertEqual(scan_table.scan.call_count, 2)

    def test_feedback_stats_can_aggregate_from_dynamodb_style_items(self):
        items = [
            {
                "id": "1",
                "question": "Q1",
                "user_rating": "negative",
                "reviewed": False,
                "approved_for_training": False,
                "needs_review": True,
                "confidence_score": 55,
                "timestamp": "2026-04-14T10:00:00",
            },
            {
                "id": "2",
                "question": "Q2",
                "user_rating": "positive",
                "reviewed": True,
                "approved_for_training": True,
                "needs_review": False,
                "confidence_score": 88,
                "timestamp": "2026-04-14T11:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items), \
             patch.object(feedback_system, "_load_training_example_items", return_value=[{"id": "te-1"}, {"id": "te-2"}, {"id": "te-3"}]), \
             patch.object(feedback_system, "_load_feedback_items_by_type", return_value=[{"id": "run-1"}]):
            stats = feedback_system.get_feedback_stats()

        self.assertEqual(stats["total_feedback"], 2)
        self.assertEqual(stats["negative_feedback"], 1)
        self.assertEqual(stats["positive_feedback"], 1)
        self.assertEqual(stats["unreviewed_negative"], 1)
        self.assertEqual(stats["approved_for_training"], 1)
        self.assertEqual(stats["examples_ready"], 3)
        self.assertEqual(stats["training_runs"], 1)

    def test_feedback_stats_use_dynamodb_training_examples_and_runs(self):
        feedback_items = [
            {
                "id": "1",
                "question": "Q1",
                "user_rating": "positive",
                "reviewed": True,
                "approved_for_training": True,
                "needs_review": False,
                "confidence_score": 88,
                "timestamp": "2026-04-14T11:00:00",
            },
        ]
        training_examples = [
            {"id": "training-example:1", "feedback_id": "1", "used_in_training": False},
            {"id": "training-example:2", "feedback_id": "2", "used_in_training": False},
        ]
        training_runs = [{"id": "run-1", "item_type": "training_run"}]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=feedback_items), \
             patch.object(feedback_system, "_load_training_example_items", return_value=training_examples), \
             patch.object(feedback_system, "_load_feedback_items_by_type", return_value=training_runs):
            stats = feedback_system.get_feedback_stats()

        self.assertEqual(stats["examples_ready"], 2)
        self.assertEqual(stats["training_runs"], 1)

    def test_review_queue_can_build_from_dynamodb_style_items(self):
        items = [
            {
                "id": "1",
                "question": "Q1",
                "ai_answer": "A1",
                "user_rating": "negative",
                "user_correction": "C1",
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 40,
                "sources": [],
                "timestamp": "2026-04-14T10:00:00",
            },
            {
                "id": "2",
                "question": "Q2",
                "ai_answer": "A2",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 30,
                "sources": [],
                "timestamp": "2026-04-14T09:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_records", return_value=items):
            queue = feedback_system.get_review_queue(limit=10, queue_type="all")

        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["review_type"], "user_flagged")
        self.assertEqual(queue[1]["review_type"], "no_feedback")

    def test_review_queue_preserves_uploaded_image_attachment_metadata(self):
        items = [
            {
                "id": "1",
                "question": "Does this look like mower injury?",
                "ai_answer": "A1",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": False,
                "confidence_score": 89,
                "sources": [{"name": "Uploaded Turf Image", "type": "user_image"}],
                "attachment": {
                    "kind": "uploaded_image",
                    "name": "leaf.png",
                    "data_url": "data:image/png;base64,abc",
                },
                "timestamp": "2026-04-14T10:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_records", return_value=items):
            queue = feedback_system.get_review_queue(limit=10, queue_type="all")

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["attachment"]["kind"], "uploaded_image")
        self.assertEqual(queue[0]["attachment"]["name"], "leaf.png")

    def test_review_queue_deduplicates_duplicate_questions_in_dynamodb_mode(self):
        items = [
            {
                "id": "1",
                "question": "What fungicide should I use for dollar spot?",
                "ai_answer": "A1",
                "user_rating": "negative",
                "user_correction": "C1",
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 40,
                "sources": [],
                "timestamp": "2026-04-14T10:00:00",
            },
            {
                "id": "2",
                "question": "  What fungicide should I use for dollar spot?  ",
                "ai_answer": "A2",
                "user_rating": "negative",
                "user_correction": "C2",
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 35,
                "sources": [],
                "timestamp": "2026-04-14T09:00:00",
            },
            {
                "id": "3",
                "question": "What insecticide should I use for grubs?",
                "ai_answer": "A3",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 30,
                "sources": [],
                "timestamp": "2026-04-14T08:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items):
            queue = feedback_system.get_review_queue(limit=10, queue_type="negative")

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["question"], "What fungicide should I use for dollar spot?")
        self.assertEqual(queue[0]["duplicate_count"], 2)
        self.assertEqual(sorted(queue[0]["duplicate_feedback_ids"]), ["1", "2"])

    def test_review_queue_deduplicates_punctuation_only_question_variants(self):
        items = [
            {
                "id": "1",
                "question": "What should I spray",
                "ai_answer": "A1",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 20,
                "sources": [],
                "timestamp": "2026-04-14T10:00:00",
            },
            {
                "id": "2",
                "question": "What should I spray?",
                "ai_answer": "A2",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 18,
                "sources": [],
                "timestamp": "2026-04-14T09:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items):
            queue = feedback_system.get_review_queue(limit=10, queue_type="low_confidence")

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["duplicate_count"], 2)
        self.assertEqual(queue[0]["duplicate_feedback_ids"], ["2", "1"])

    def test_review_queue_limit_applies_after_deduplication(self):
        duplicate_items = [
            {
                "id": str(index),
                "question": "Can I tank mix Daconil and some random thing?",
                "ai_answer": f"A{index}",
                "user_rating": "negative",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 25,
                "sources": [],
                "timestamp": f"2026-04-14T10:{index:02d}:00",
            }
            for index in range(12)
        ]
        unique_item = {
            "id": "99",
            "question": "What should I use for anthracnose on greens?",
            "ai_answer": "A99",
            "user_rating": "negative",
            "user_correction": "Need a more careful answer",
            "reviewed": False,
            "needs_review": True,
            "confidence_score": 20,
            "sources": [],
            "timestamp": "2026-04-14T11:30:00",
        }
        items = [unique_item] + duplicate_items
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items):
            queue = feedback_system.get_review_queue(limit=5, queue_type="negative")

        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["question"], "What should I use for anthracnose on greens?")
        self.assertEqual(queue[1]["duplicate_count"], 12)

    def test_priority_review_queue_deduplicates_before_final_limit(self):
        duplicate_items = [
            {
                "id": str(index),
                "question": "Can I use Xzemplar for anthracnose?",
                "ai_answer": f"A{index}",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 18,
                "sources": [],
                "timestamp": f"2026-04-14T10:{index:02d}:00",
            }
            for index in range(15)
        ]
        unique_item = {
            "id": "200",
            "question": "What is Headway used for?",
            "ai_answer": "A200",
            "user_rating": "negative",
            "user_correction": "Need supported diseases first",
            "reviewed": False,
            "needs_review": True,
            "confidence_score": 42,
            "sources": [],
            "timestamp": "2026-04-14T11:45:00",
        }
        items = [unique_item] + duplicate_items
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items):
            queue = feedback_system.get_priority_review_queue(limit=5)

        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["question"], "What is Headway used for?")
        self.assertEqual(queue[1]["duplicate_count"], 15)

    def test_expert_router_stats_can_aggregate_from_dynamodb_style_items(self):
        items = [
            {
                "id": "evt-1",
                "question": "Why is bentgrass struggling?",
                "selected_mode": "advanced_turf_science",
                "resolved_mode": "advanced_diagnosis",
                "used_deterministic": True,
                "needs_review": True,
                "router_confidence": 0.61,
                "created_at": "2026-04-14T11:00:00",
            },
            {
                "id": "evt-2",
                "question": "What should I use for dollar spot on greens?",
                "selected_mode": "verified_product",
                "resolved_mode": "verified_product",
                "used_deterministic": True,
                "needs_review": False,
                "router_confidence": 0.92,
                "created_at": "2026-04-14T10:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items_by_type", return_value=items), \
             patch.object(feedback_system, "get_expert_router_backlog", return_value=[]), \
             patch.object(feedback_system, "_build_router_improvement_suggestion", return_value={"type": "science_topic"}):
            stats = feedback_system.get_expert_router_stats()

        self.assertEqual(stats["total_events"], 2)
        self.assertEqual(stats["deterministic_hits"], 2)
        self.assertEqual(stats["needs_review"], 1)
        self.assertEqual(stats["fallback_events"], 1)
        self.assertEqual(stats["avg_router_confidence"], 0.77)

    def test_router_work_items_can_round_trip_from_dynamodb_style_items(self):
        stored = {}

        def fake_get(item_id, expected_type=None):
            item = stored.get(item_id)
            if item and (expected_type is None or item.get("item_type") == expected_type):
                return item.copy()
            return None

        def fake_save(item):
            stored[item["id"]] = item.copy()

        backlog = [{
            "pattern_key": "science:summer_stress",
            "type": "science_topic",
            "title": "Summer stress aliases",
            "summary": "Capture broad summer stress phrasing.",
            "action": "Expand science aliases.",
            "count": 3,
            "sample_questions": ["What causes bentgrass to decline in summer?"],
            "gap_ids": [],
        }]

        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "get_expert_router_backlog", return_value=backlog), \
             patch.object(feedback_system, "_save_feedback_item", side_effect=fake_save), \
             patch.object(feedback_system, "_load_feedback_item_by_id", side_effect=fake_get), \
             patch.object(feedback_system, "get_expert_router_work_items", return_value=[]):
            created = feedback_system.create_expert_router_work_item("science:summer_stress")
            self.assertTrue(created["success"])
            work_item_id = created["id"]

            updated = feedback_system.update_expert_router_work_item_status(work_item_id, "in_progress")
            self.assertTrue(updated["success"])

            draft = feedback_system.generate_expert_router_work_item_draft(work_item_id)
            self.assertTrue(draft["success"])
            self.assertEqual(draft["draft_type"], "science_note")
            self.assertEqual(stored[work_item_id]["status"], "in_progress")
            self.assertEqual(stored[work_item_id]["draft_type"], "science_note")

    def test_approve_for_training_reuses_existing_dynamodb_training_example(self):
        stored = {
            "feedback-1": {
                "id": "feedback-1",
                "item_type": "feedback",
                "question": "What fungicide should I use?",
                "ai_answer": "Old answer",
                "timestamp": "2026-04-14T10:00:00",
                "reviewed": False,
                "approved_for_training": False,
            },
            "training-example:feedback-1": {
                "id": "training-example:feedback-1",
                "item_type": "training_example",
                "feedback_id": "feedback-1",
                "question": "What fungicide should I use?",
                "ideal_answer": "First answer",
                "created_at": "2026-04-14T10:00:00",
                "used_in_training": False,
                "training_run_id": None,
            },
        }

        def fake_get(item_id, expected_type=None):
            item = stored.get(str(item_id))
            if not item:
                return None
            if expected_type and item.get("item_type") != expected_type:
                return None
            return item.copy()

        def fake_save(item):
            stored[item["id"]] = item.copy()

        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_item_by_id", side_effect=fake_get), \
             patch.object(feedback_system, "_save_feedback_item", side_effect=fake_save), \
             patch.object(feedback_system, "_save_moderator_action_item", return_value="mod-1"):
            approved = feedback_system.approve_for_training("feedback-1", "Updated answer")

        self.assertTrue(approved)
        self.assertEqual(stored["training-example:feedback-1"]["ideal_answer"], "Updated answer")
        training_example_ids = [key for key in stored if key.startswith("training-example:")]
        self.assertEqual(training_example_ids, ["training-example:feedback-1"])

    def test_bulk_auto_approve_skips_negative_feedback_in_dynamodb_mode(self):
        items = [
            {
                "id": "negative-item",
                "question": "Q1",
                "confidence_score": 92,
                "reviewed": False,
                "user_rating": "negative",
            },
            {
                "id": "positive-item",
                "question": "Q2",
                "confidence_score": 92,
                "reviewed": False,
                "user_rating": "positive",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_records", return_value=items), \
             patch.object(feedback_system, "bulk_moderate", return_value={"success": 1, "failed": 0}) as bulk_moderate:
            result = feedback_system.bulk_approve_high_confidence(min_confidence=80, limit=10)

        self.assertEqual(result["success"], 1)
        bulk_moderate.assert_called_once()
        args = bulk_moderate.call_args.args
        self.assertEqual(args[0], ["positive-item"])

    def test_get_all_feedback_normalizes_recent_records(self):
        items = [
            {
                "id": "1",
                "question": "Q1",
                "ai_answer": "A1",
                "user_rating": "positive",
                "user_correction": None,
                "timestamp": "2026-04-14T10:00:00",
                "confidence_score": 84,
            }
        ]
        with patch.object(feedback_system, "_load_feedback_records", return_value=items):
            feed = feedback_system.get_all_feedback(limit=100)

        self.assertEqual(feed[0]["rating"], "positive")
        self.assertEqual(feed[0]["confidence"], 84)

    def test_queries_needing_review_can_build_from_dynamodb_style_items(self):
        items = [
            {
                "id": "1",
                "question": "Q1",
                "ai_answer": "A1",
                "confidence_score": 62,
                "sources": ["s1"],
                "timestamp": "2026-04-14T10:00:00",
                "reviewed": False,
                "needs_review": True,
            },
            {
                "id": "2",
                "question": "Q2",
                "ai_answer": "A2",
                "confidence_score": 90,
                "sources": [],
                "timestamp": "2026-04-14T11:00:00",
                "reviewed": True,
                "needs_review": True,
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items):
            queue = feedback_system.get_queries_needing_review(limit=10)

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["id"], "1")

    def test_priority_review_queue_can_build_from_dynamodb_style_items(self):
        items = [
            {
                "id": "1",
                "question": "Why are greens soft?",
                "ai_answer": "A1",
                "user_rating": "negative",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 42,
                "sources": [],
                "timestamp": "2026-04-14T10:00:00",
            },
            {
                "id": "2",
                "question": "Why are greens soft?",
                "ai_answer": "A2",
                "user_rating": "unrated",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 55,
                "sources": [],
                "timestamp": "2026-04-14T09:00:00",
            },
            {
                "id": "3",
                "question": "Why are greens soft?",
                "ai_answer": "A3",
                "user_rating": "positive",
                "user_correction": None,
                "reviewed": False,
                "needs_review": True,
                "confidence_score": 61,
                "sources": [],
                "timestamp": "2026-04-14T08:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items):
            queue = feedback_system.get_priority_review_queue(limit=10)

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["id"], "1")
        self.assertEqual(queue[0]["frequency"], 3)
        self.assertTrue(queue[0]["is_trending"])
        self.assertEqual(queue[0]["duplicate_count"], 3)

    def test_trending_issues_can_build_from_dynamodb_style_items(self):
        items = [
            {
                "id": "1",
                "question": "Why are greens soft?",
                "user_rating": "negative",
                "confidence_score": 44,
                "timestamp": "2026-04-14T10:00:00",
            },
            {
                "id": "2",
                "question": "Why are greens soft?",
                "user_rating": "unrated",
                "confidence_score": 51,
                "timestamp": "2026-04-14T11:00:00",
            },
            {
                "id": "3",
                "question": "Why are greens soft?",
                "user_rating": "negative",
                "confidence_score": 60,
                "timestamp": "2026-04-14T12:00:00",
            },
        ]
        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_items", return_value=items), \
             patch.object(feedback_system, "datetime") as fake_datetime:
            fake_datetime.now.return_value = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
            fake_datetime.fromisoformat.side_effect = datetime.fromisoformat
            trending = feedback_system.get_trending_issues(min_frequency=3, days=7)

        self.assertEqual(len(trending), 1)
        self.assertEqual(trending[0]["question"], "why are greens soft?")
        self.assertEqual(trending[0]["severity"], "high")

    def test_training_run_records_can_round_trip_from_dynamodb_style_items(self):
        stored = {}

        def fake_get(item_id, expected_type=None):
            item = stored.get(str(item_id))
            if not item:
                return None
            if expected_type and item.get("item_type") != expected_type:
                return None
            return item.copy()

        def fake_save(item):
            stored[item["id"]] = item.copy()

        with patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=True), \
             patch.object(feedback_system, "_load_feedback_item_by_id", side_effect=fake_get), \
             patch.object(feedback_system, "_save_feedback_item", side_effect=fake_save):
            feedback_system.create_training_run("run-123", 42, "Model: turf-v1")
            feedback_system.update_training_run("run-123", "completed", "ft:turf-v1")

        self.assertIn("run-123", stored)
        self.assertEqual(stored["run-123"]["item_type"], "training_run")
        self.assertEqual(stored["run-123"]["num_examples"], 42)
        self.assertEqual(stored["run-123"]["status"], "completed")
        self.assertEqual(stored["run-123"]["model_id"], "ft:turf-v1")
        self.assertIsNotNone(stored["run-123"]["completed_at"])
