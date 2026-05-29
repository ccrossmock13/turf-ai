import unittest
import uuid
import tempfile
import os
import sqlite3
from unittest.mock import Mock, patch

import app as app_module
from app import RATE_LIMIT_BUCKETS, app, Config
from auth_store import create_account, mark_email_verified
import feedback_system
from feedback_system import create_kb_regression_test, get_kb_regression_tests, save_expert_router_event, save_kb_gap


class OperationalRouteTests(unittest.TestCase):
    def setUp(self):
        RATE_LIMIT_BUCKETS.clear()
        self.client = app.test_client()
        self.csrf_token = "test-csrf-token"
        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
        password = "StrongPass123!"
        account, error = create_account(
            email,
            password,
            name="Test Admin",
            organization="Test Org",
            accepted_terms=True,
            accepted_privacy=True,
            role="admin",
        )
        self.assertIsNone(error)
        self.assertIsNotNone(account)
        mark_email_verified(account["id"])
        self.account = {
            **account,
            "email_verified_at": "2026-01-01T00:00:00+00:00",
            "status": "active",
        }
        self.current_account_patcher = patch("app._current_account", return_value=self.account)
        self.current_account_patcher.start()
        with self.client.session_transaction() as session:
            session["_csrf_token"] = self.csrf_token
            session["_permanent"] = True
            session["account_id"] = account["id"]
            session["account_email"] = account["email"]
            session["account_role"] = account.get("role", "admin")
            session["account_name"] = account.get("name", "")
            session["account_org"] = account.get("organization", "")

    def tearDown(self):
        if hasattr(self, "current_account_patcher"):
            self.current_account_patcher.stop()

    def _csrf_token(self, client):
        return self.csrf_token

    def post(self, client, path, *, json=None, data=None, **kwargs):
        token = self._csrf_token(client)
        if json is not None:
            payload = dict(json)
            payload.setdefault("csrf_token", token)
            return client.post(path, json=payload, **kwargs)
        if data is not None:
            payload = dict(data)
            payload.setdefault("_csrf_token", token)
            return client.post(path, data=payload, **kwargs)
        return client.post(path, json={"csrf_token": token}, **kwargs)

    def test_operational_question_uses_profile_snapshot(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should we focus on this month?"})
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["confidence"]["label"], "Current Priorities")
            self.assertIn("This is the current management snapshot", payload["answer"])
            self.assertIn("Surface-specific next actions:", payload["answer"])
            self.assertIn("**Greens (creeping bentgrass)**", payload["answer"])
            self.assertTrue(payload.get("operational_guidance"))

    def test_public_page_routes_have_single_owner(self):
        endpoints_by_path = {}
        for rule in app.url_map.iter_rules():
            endpoints_by_path.setdefault(rule.rule, []).append(rule.endpoint)

        for path in (
            "/",
            "/resources",
            "/api/resources",
            "/epa_labels/<path:filename>",
            "/product-labels/<path:filename>",
            "/solution-sheets/<path:filename>",
            "/spray-programs/<path:filename>",
            "/ntep-pdfs/<path:filename>",
        ):
            with self.subTest(path=path):
                self.assertEqual(len(endpoints_by_path.get(path, [])), 1)

    def test_ready_returns_200_when_release_requirements_are_present(self):
        with tempfile.TemporaryDirectory(prefix="greenside-ready-") as temp_dir:
            with patch.object(Config, "FLASK_SECRET_KEY", "release-secret-key"), \
                 patch.object(Config, "OPENAI_API_KEY", "ready-openai-key"), \
                 patch.object(Config, "PINECONE_API_KEY", "ready-pinecone-key"), \
                 patch.object(Config, "SMTP_HOST", "smtp.example.com"), \
                 patch.object(Config, "MAIL_FROM", "alerts@example.com"), \
                 patch.object(Config, "DATA_DIR", temp_dir), \
                 patch.object(Config, "DEPLOYMENT_MODE", "single_node_persistent"), \
                 patch.object(Config, "ENFORCE_KB_TRUST_GATE", False):
                response = self.client.get("/ready")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["status"], "ready")
                self.assertEqual(payload["deployment_mode"], "single_node_persistent")
                self.assertTrue(all(payload["checks"].values()))

    def test_ready_accepts_local_sendmail_as_password_reset_delivery(self):
        with tempfile.TemporaryDirectory(prefix="greenside-ready-") as temp_dir:
            with patch.object(Config, "FLASK_SECRET_KEY", "release-secret-key"), \
                 patch.object(Config, "OPENAI_API_KEY", "ready-openai-key"), \
                 patch.object(Config, "PINECONE_API_KEY", "ready-pinecone-key"), \
                 patch.object(Config, "SMTP_HOST", None), \
                 patch.object(Config, "MAIL_FROM", "noreply@localhost"), \
                 patch.object(Config, "DATA_DIR", temp_dir), \
                 patch.object(Config, "DEPLOYMENT_MODE", "single_node_persistent"), \
                 patch.object(Config, "ENFORCE_KB_TRUST_GATE", False), \
                 patch("app._local_sendmail_path", return_value="/usr/sbin/sendmail"):
                response = self.client.get("/ready")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertTrue(payload["checks"]["password_reset_email_configured"])

    def test_ready_can_fail_when_kb_trust_gate_is_enforced_and_thresholds_are_not_met(self):
        with tempfile.TemporaryDirectory(prefix="greenside-ready-") as temp_dir:
            with patch.object(Config, "FLASK_SECRET_KEY", "release-secret-key"), \
                 patch.object(Config, "OPENAI_API_KEY", "ready-openai-key"), \
                 patch.object(Config, "PINECONE_API_KEY", "ready-pinecone-key"), \
                 patch.object(Config, "SMTP_HOST", "smtp.example.com"), \
                 patch.object(Config, "MAIL_FROM", "alerts@example.com"), \
                 patch.object(Config, "DATA_DIR", temp_dir), \
                 patch.object(Config, "DEPLOYMENT_MODE", "single_node_persistent"), \
                 patch.object(Config, "ENFORCE_KB_TRUST_GATE", True), \
                 patch.object(Config, "KB_TRUST_MIN_HUMAN_REVIEW_PERCENT", 90.0):
                response = self.client.get("/ready")
                self.assertEqual(response.status_code, 503)
                payload = response.get_json()
                self.assertEqual(payload["status"], "not_ready")
                self.assertFalse(payload["checks"]["kb_trust_gate_passed"])
                self.assertEqual(payload["kb_trust_gate"]["status"], "fail")

    def test_ready_fails_when_email_verification_is_required_without_mail_delivery(self):
        with tempfile.TemporaryDirectory(prefix="greenside-ready-") as temp_dir:
            with patch.object(Config, "FLASK_SECRET_KEY", "release-secret-key"), \
                 patch.object(Config, "OPENAI_API_KEY", "ready-openai-key"), \
                 patch.object(Config, "PINECONE_API_KEY", "ready-pinecone-key"), \
                 patch.object(Config, "SMTP_HOST", None), \
                 patch.object(Config, "MAIL_FROM", None), \
                 patch.object(Config, "DATA_DIR", temp_dir), \
                 patch.object(Config, "DEPLOYMENT_MODE", "single_node_persistent"), \
                 patch.object(Config, "ENFORCE_KB_TRUST_GATE", False), \
                 patch.object(Config, "REQUIRE_EMAIL_VERIFICATION", True):
                response = self.client.get("/ready")
                self.assertEqual(response.status_code, 503)
                payload = response.get_json()
                self.assertFalse(payload["checks"]["email_verification_delivery_ready"])

    def test_ready_fails_when_public_admin_is_enabled(self):
        with tempfile.TemporaryDirectory(prefix="greenside-ready-") as temp_dir:
            with patch.object(Config, "FLASK_SECRET_KEY", "release-secret-key"), \
                 patch.object(Config, "OPENAI_API_KEY", "ready-openai-key"), \
                 patch.object(Config, "PINECONE_API_KEY", "ready-pinecone-key"), \
                 patch.object(Config, "SMTP_HOST", "smtp.example.com"), \
                 patch.object(Config, "MAIL_FROM", "alerts@example.com"), \
                 patch.object(Config, "DATA_DIR", temp_dir), \
                 patch.object(Config, "DEPLOYMENT_MODE", "single_node_persistent"), \
                 patch.object(Config, "ENFORCE_KB_TRUST_GATE", False), \
                 patch.object(Config, "ALLOW_PUBLIC_ADMIN", True):
                response = self.client.get("/ready")
                self.assertEqual(response.status_code, 503)
                payload = response.get_json()
                self.assertEqual(payload["status"], "not_ready")
                self.assertFalse(payload["checks"]["admin_auth_locked_down"])
                self.assertTrue(any("ALLOW_PUBLIC_ADMIN=true" in warning for warning in payload["warnings"]))

    def test_password_reset_email_uses_local_sendmail_when_smtp_is_absent(self):
        with patch.object(Config, "SMTP_HOST", None), \
             patch.object(Config, "MAIL_FROM", "noreply@localhost"), \
             patch("app._local_sendmail_path", return_value="/usr/sbin/sendmail"), \
             patch("app.subprocess.run") as run_sendmail:
            self.assertTrue(app_module._send_password_reset_email("user@example.com", "http://localhost/reset"))

        run_sendmail.assert_called_once()

    def test_ready_reports_missing_dynamodb_tables_when_backend_is_dynamodb(self):
        with tempfile.TemporaryDirectory(prefix="greenside-ready-") as temp_dir:
            with patch.object(Config, "FLASK_SECRET_KEY", "release-secret-key"), \
                 patch.object(Config, "OPENAI_API_KEY", "ready-openai-key"), \
                 patch.object(Config, "PINECONE_API_KEY", "ready-pinecone-key"), \
                 patch.object(Config, "SMTP_HOST", "smtp.example.com"), \
                 patch.object(Config, "MAIL_FROM", "alerts@example.com"), \
                 patch.object(Config, "DATA_DIR", temp_dir), \
                 patch.object(Config, "DEPLOYMENT_MODE", "managed_storage"), \
                 patch.object(Config, "PERSISTENCE_BACKEND", "dynamodb"), \
                 patch.object(Config, "AWS_REGION", "us-east-1"), \
                 patch("app.dynamodb_table_exists", return_value=False):
                response = self.client.get("/ready")
                self.assertEqual(response.status_code, 503)
                payload = response.get_json()
                self.assertFalse(payload["checks"]["dynamodb_tables_ready"])
                self.assertIn("dynamodb_tables", payload)
                self.assertFalse(payload["dynamodb_tables"]["accounts"]["exists"])

    def test_operational_question_can_target_one_surface(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should we do on greens this month?"})
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["confidence"]["label"], "Surface-Specific Priorities")
            self.assertIn("**Greens (creeping bentgrass)**", payload["answer"])
            self.assertNotIn("**Fairways (kentucky bluegrass)**", payload["answer"])

    def test_kb_quality_dashboard_includes_trust_gate(self):
        response = self.client.get("/admin/kb-quality-dashboard")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("trust_gate", payload)
        self.assertIn("checks", payload["trust_gate"])
        self.assertIn("status", payload["trust_gate"])

    def test_kb_trust_gate_uses_trust_blocking_gap_count(self):
        payload = app_module._kb_trust_gate_payload({
            "summary": {
                "human_review_coverage_percent": 40.0,
                "warning_records": 0,
                "open_kb_gaps": 12,
                "trust_blocking_open_kb_gaps": 0,
            },
            "all_fields": [
                {"field": "rei", "coverage_percent": 90.0},
                {"field": "irrigation_guidance", "coverage_percent": 100.0},
                {"field": "tank_mix_guidance", "coverage_percent": 95.0},
                {"field": "max_rate_per_app", "coverage_percent": 88.0},
            ],
        })

        self.assertEqual(payload["status"], "pass")
        open_gap_check = next(item for item in payload["checks"] if item["key"] == "open_kb_gaps")
        self.assertEqual(open_gap_check["actual"], 0)
        self.assertTrue(open_gap_check["passed"])

    def test_admin_feedback_all_uses_backend_aware_feedback_feed(self):
        expected = [{
            "id": "fb-1",
            "question": "What should I spray?",
            "ai_answer": "Use Product X",
            "rating": "negative",
            "correction": "Need surface first",
            "timestamp": "2026-04-14T10:00:00",
            "confidence": 54,
        }]
        with patch("feedback_system.get_all_feedback", return_value=expected) as get_all_feedback:
            response = self.client.get("/admin/feedback/all")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)
        get_all_feedback.assert_called_once_with(limit=100)

    def test_admin_review_queue_returns_paged_payload(self):
        expected_page = {
            "items": [
                {"id": "fb-2", "question": "Q2", "ai_answer": "A2"},
                {"id": "fb-3", "question": "Q3", "ai_answer": "A3"},
            ],
            "total": 3,
            "offset": 1,
            "limit": 2,
            "next_offset": 3,
            "has_more": False,
        }
        with patch("feedback_system.get_feedback_feed_page", return_value=expected_page) as get_feedback_feed_page:
            response = self.client.get("/admin/review-queue?type=all&limit=2&offset=1")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload, expected_page)
        get_feedback_feed_page.assert_called_once_with(limit=2, offset=1)

    def test_only_product_labels_are_publicly_served(self):
        blocked_paths = (
            "/epa_labels/example.pdf",
            "/solution-sheets/example.pdf",
            "/spray-programs/example.pdf",
            "/ntep-pdfs/example.pdf",
        )
        for path in blocked_paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)

    def test_get_pinecone_index_safe_caches_dns_failure(self):
        with patch.object(app_module, "_pinecone_index", None), \
             patch.object(app_module, "_pinecone_unavailable_until", 0.0), \
             patch("app.get_pinecone_index", side_effect=RuntimeError("dns failure")) as get_index, \
             patch("app.logger.warning"), \
             patch("app.time.time", side_effect=[100.0, 110.0, 170.0]):
            self.assertIsNone(app_module.get_pinecone_index_safe())
            self.assertIsNone(app_module.get_pinecone_index_safe())
            self.assertIsNone(app_module.get_pinecone_index_safe())

        self.assertEqual(get_index.call_count, 2)

    def test_product_label_route_serves_allowed_pdf(self):
        allowed = self.client.get("/product-labels/Acelepryn%20G%20label.pdf")
        try:
            self.assertEqual(allowed.status_code, 200)
        finally:
            allowed.close()

    def test_resources_api_returns_product_labels_and_safe_public_links(self):
        response = self.client.get("/api/resources")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload)
        self.assertTrue(any(item["url"].startswith("/static/product-labels/") for item in payload))
        self.assertTrue(all(
            item["url"].startswith("https://") or item["url"].startswith("/static/product-labels/")
            for item in payload
        ))

    def test_ask_uses_deterministic_fallback_when_openai_is_unavailable(self):
        with patch("app.openai_requests_available", return_value=False):
            response = self.post(self.client, "/ask", json={"question": "How do I keep bentgrass alive in August?"})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("kb_verdict"), "general_turf_guidance")
        self.assertIn("Bottom Line", payload.get("answer", ""))

    def test_ask_handles_non_object_json_body_without_server_error(self):
        response = self.client.post(
            "/ask",
            data='["not", "an", "object"]',
            content_type="application/json",
            headers={"X-CSRF-Token": self.csrf_token},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("Please enter a question", payload["answer"])

    def test_feedback_handles_non_object_json_body_without_server_error(self):
        response = self.client.post(
            "/feedback",
            data='["not", "an", "object"]',
            content_type="application/json",
            headers={"X-CSRF-Token": self.csrf_token},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Invalid feedback rating")

    def test_feedback_updates_existing_query_row_without_creating_a_duplicate(self):
        with tempfile.TemporaryDirectory(prefix="feedback-route-") as temp_dir:
            db_path = os.path.join(temp_dir, "feedback.db")
            with patch.object(feedback_system, "DB_PATH", db_path), \
                 patch.object(feedback_system, "_feedback_runtime_uses_dynamodb", return_value=False), \
                 patch("app.openai_requests_available", return_value=False), \
                 patch("fine_tuning.track_source_quality", return_value=None):
                feedback_system.init_feedback_database()

                ask_response = self.post(self.client, "/ask", json={"question": "How do I keep bentgrass alive in August?"})
                self.assertEqual(ask_response.status_code, 200)
                ask_payload = ask_response.get_json()
                self.assertIsNotNone(ask_payload.get("feedback_id"))

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM feedback")
                self.assertEqual(cursor.fetchone()[0], 1)
                conn.close()

                feedback_response = self.post(
                    self.client,
                    "/feedback",
                    json={
                        "feedback_id": ask_payload["feedback_id"],
                        "question": "How do I keep bentgrass alive in August?",
                        "answer": ask_payload["answer"],
                        "rating": "positive",
                    },
                )
                self.assertEqual(feedback_response.status_code, 200)

                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM feedback")
                self.assertEqual(cursor.fetchone()[0], 1)
                cursor.execute("SELECT id, user_rating FROM feedback")
                row = cursor.fetchone()
                conn.close()

                self.assertEqual(row[0], ask_payload["feedback_id"])
                self.assertEqual(row[1], "positive")

    def test_admin_moderate_handles_non_object_json_body_without_server_error(self):
        response = self.client.post(
            "/admin/moderate",
            data='["not", "an", "object"]',
            content_type="application/json",
            headers={"X-CSRF-Token": self.csrf_token},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Missing moderation id or action")

    def test_admin_moderate_rejects_unknown_action(self):
        response = self.post(self.client, "/admin/moderate", json={"id": "fb-1", "action": "explode"})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Invalid moderation action")

    def test_admin_bulk_moderate_rejects_invalid_action(self):
        response = self.post(self.client, "/admin/bulk-moderate", json={"ids": ["fb-1"], "action": "explode"})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Invalid bulk action")

    def test_admin_bulk_moderate_ignores_blank_and_non_scalar_ids(self):
        with patch("feedback_system.bulk_moderate", return_value={"success": 1, "failed": 0}) as bulk_moderate:
            response = self.post(
                self.client,
                "/admin/bulk-moderate",
                json={"ids": ["fb-1", " ", None, {"bad": "id"}, 22], "action": "approve"},
            )

        self.assertEqual(response.status_code, 200)
        bulk_moderate.assert_called_once_with(["fb-1", "22"], "approve", None, moderator=self.account["email"])

    def test_admin_bulk_approve_high_confidence_clamps_inputs(self):
        with patch("feedback_system.bulk_approve_high_confidence", return_value={"success": 0, "failed": 0}) as bulk_auto:
            response = self.post(
                self.client,
                "/admin/bulk-approve-high-confidence",
                json={"min_confidence": 999, "limit": -5},
            )

        self.assertEqual(response.status_code, 200)
        bulk_auto.assert_called_once_with(100, 1, moderator=self.account["email"])

    def test_admin_generate_training_respects_real_minimum_threshold(self):
        generator = Mock(return_value=None)
        with patch("feedback_system.generate_training_file", generator), \
             patch("fine_tuning.MIN_EXAMPLES_FOR_TRAINING", 50):
            response = self.post(self.client, "/admin/training/generate")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        generator.assert_called_once_with(min_examples=50)

    def test_admin_moderation_routes_use_logged_in_moderator_identity(self):
        with patch("feedback_system.approve_for_training", return_value=True) as approve_feedback, \
             patch("feedback_system.reject_feedback", return_value=True) as reject_feedback, \
             patch("feedback_system.moderate_answer", return_value={"success": True}) as moderate_answer, \
             patch("feedback_system.bulk_moderate", return_value={"success": 1, "failed": 0}) as bulk_moderate, \
             patch("feedback_system.bulk_approve_high_confidence", return_value={"success": 1, "failed": 0}) as bulk_auto:
            approve_response = self.post(self.client, "/admin/feedback/approve", json={"id": "fb-1", "correction": "Better answer"})
            reject_response = self.post(self.client, "/admin/feedback/reject", json={"id": "fb-2", "notes": "Not safe enough"})
            moderate_response = self.post(self.client, "/admin/moderate", json={"id": "fb-3", "action": "reject"})
            bulk_response = self.post(self.client, "/admin/bulk-moderate", json={"ids": ["fb-4"], "action": "approve"})
            auto_response = self.post(self.client, "/admin/bulk-approve-high-confidence", json={"min_confidence": 80, "limit": 10})

        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(moderate_response.status_code, 200)
        self.assertEqual(bulk_response.status_code, 200)
        self.assertEqual(auto_response.status_code, 200)

        moderator_email = "admin"
        with self.client.session_transaction() as session:
            moderator_email = session.get("account_email")

        approve_feedback.assert_called_once_with("fb-1", "Better answer", moderator=moderator_email)
        reject_feedback.assert_called_once_with("fb-2", "Not safe enough", moderator=moderator_email)
        moderate_kwargs = moderate_answer.call_args.kwargs
        self.assertEqual(moderate_kwargs["moderator"], moderator_email)
        bulk_moderate.assert_called_once_with(["fb-4"], "approve", None, moderator=moderator_email)
        bulk_auto.assert_called_once_with(80, 10, moderator=moderator_email)

    def test_operational_spray_question_no_longer_hits_need_more_info_when_profile_exists(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Atlanta, Georgia",
                    "surfaces": {
                        "greens": "",
                        "fairways": "bermudagrass",
                        "tees": "bermudagrass",
                        "rough": "zoysiagrass",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should I spray this month?"})
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["confidence"]["label"], "Profile-Based Spray Guidance")
            self.assertNotEqual(payload["confidence"]["label"], "Need More Info")
            self.assertIn("I would not jump straight to a product list", payload["answer"])

    def test_surface_target_question_returns_verified_product_options(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should I use for dollar spot on greens?"})
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified_surface_target_options")
            self.assertEqual(payload["confidence"]["label"], "Verified Surface-Target Options")
            self.assertEqual(payload["expert_router"]["mode"], "verified_product")
            self.assertIn("Daconil", payload["answer"])
            self.assertFalse(payload["needs_review"])

    def test_surface_target_question_can_use_saved_turf_name_as_surface_hint(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(
                client,
                "/ask",
                json={"question": "What fungicide should I use for dollar spot on bentgrass?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified_surface_target_options")
            self.assertEqual(payload["confidence"]["label"], "Verified Surface-Target Options")
            self.assertEqual(payload["expert_router"]["mode"], "verified_product")
            self.assertIn("Daconil", payload["answer"])
            self.assertNotEqual(payload["kb_verdict"], "safety_blocked")

    def test_surface_target_question_without_saved_surface_returns_context_needed_not_safety_block(self):
        with self.client as client:
            response = self.post(
                client,
                "/ask",
                json={"question": "What fungicide should I use for dollar spot on bentgrass?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "needs_more_context")
            self.assertEqual(payload["confidence"]["label"], "Needs More Context")
            self.assertIn("surface", payload["answer"].lower())
            self.assertNotEqual(payload["kb_verdict"], "safety_blocked")

    def test_conflicting_surface_turf_question_returns_context_needed_not_wrong_surface_answer(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(
                client,
                "/ask",
                json={"question": "What can I spray for dollar spot on bentgrass fairways?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "needs_more_context")
            self.assertEqual(payload["confidence"]["label"], "Needs More Context")
            self.assertIn("saved profile says", payload["answer"].lower())
            self.assertNotEqual(payload["kb_verdict"], "verified_surface_target_options")

    def test_unsupported_tank_mix_question_is_blocked_by_safety_gate(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Can I tank mix Daconil and some random thing?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "safety_blocked")
            self.assertEqual(payload["confidence"]["label"], "Need Verified Support")
            self.assertFalse(payload["needs_review"])
            self.assertIn("tank-mix", payload["answer"].lower())

    def test_missing_context_rate_question_is_blocked_by_safety_gate(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "What rate of Daconil should I use?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified KB Rate Summary")
            self.assertIn("rates currently stored", payload["answer"].lower())

    def test_diagnosis_confirmation_question_is_blocked_without_review_queue_churn(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "This is definitely pythium right?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "safety_blocked")
            self.assertEqual(payload["confidence"]["label"], "Needs Field Confirmation")
            self.assertFalse(payload["needs_review"])
            self.assertIn("should not confirm a disease", payload["answer"].lower())

    def test_vague_pgr_rate_question_returns_deterministic_context_needed(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "bermudagrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "How much Primo should I use?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "needs_more_context")
            self.assertEqual(payload["confidence"]["label"], "Needs More Context")
            self.assertEqual(payload["expert_router"]["selected_mode"], "verified_product")
            self.assertIn("surface", payload["answer"].lower())

    def test_mystery_disease_spray_question_returns_deterministic_context_needed(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should I spray on greens for a mystery disease?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "needs_more_context")
            self.assertEqual(payload["confidence"]["label"], "Needs More Context")
            self.assertEqual(payload["expert_router"]["selected_mode"], "verified_product")
            self.assertIn("symptoms or target disease", payload["answer"].lower())

    def test_vague_greens_struggling_question_returns_clarifying_diagnosis(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "Why are my greens struggling?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "clarifying_questions")
            self.assertEqual(payload["confidence"]["label"], "Clarifying Diagnosis")
            self.assertIn("Course context I'm using", payload["answer"])
            self.assertIn("Root condition", payload["answer"])
            self.assertNotEqual(payload["confidence"]["label"], "Need More Info")

    def test_water_or_disease_question_returns_clarifying_diagnosis_not_safety_block(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "Is this water or disease?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "clarifying_questions")
            self.assertEqual(payload["confidence"]["label"], "Clarifying Diagnosis")
            self.assertIn("Leaf evidence", payload["answer"])
            self.assertIn("Moisture and roots", payload["answer"])
            self.assertNotEqual(payload["kb_verdict"], "safety_blocked")

    def test_syringe_relief_prompt_gets_specific_clarifying_triage(self):
        with self.client as client:
            response = self.post(
                client,
                "/ask",
                json={"question": "We syringe and it helps for an hour. What does that tell you?"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "clarifying_questions")
            self.assertEqual(payload["confidence"]["label"], "Clarifying Diagnosis")
            self.assertIn("Relief pattern", payload["answer"])
            self.assertIn("canopy is buying time", payload["answer"])
            self.assertNotIn("Most useful next details", payload["answer"])

    def test_flat_green_after_disease_apps_gets_recovery_capacity_triage(self):
        with self.client as client:
            response = self.post(
                client,
                "/ask",
                json={"question": "Disease app looks fine on paper but the green still has no life. What are you checking?"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "clarifying_questions")
            self.assertEqual(payload["confidence"]["label"], "Clarifying Diagnosis")
            self.assertIn("Recovery capacity", payload["answer"])
            self.assertIn("another product", payload["answer"])
            self.assertNotIn("Most useful next details", payload["answer"])

    def test_rei_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "What is the reentry interval for Daconil?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertIn("12 hours", payload["answer"])

    def test_re_treatment_interval_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "What is the retreatment interval for Daconil?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified Re-Treatment Interval")
            self.assertIn("7 days", payload["answer"])

    def test_irrigation_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Do I need to water in Primo MAXX after application?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified Irrigation Guidance")
            self.assertIn("watering-in is not necessary", payload["answer"].lower())

    def test_rainfast_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Is Primo MAXX rainfast?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified Rainfast Guidance")
            self.assertIn("one hour", payload["answer"].lower())

    def test_max_rate_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "What is the max single application rate for Tenacity?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified Max Application Rate")
            self.assertIn("8 fl oz", payload["answer"].lower())

    def test_reseeding_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "How long after Dimension can I reseed?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified Reseeding Interval")
            self.assertIn("3 months", payload["answer"].lower())

    def test_image_upload_validation_rejects_bad_payload(self):
        with self.client as client:
            response = self.post(
                client,
                "/ask",
                json={"question": "Please assess this", "attachment": {"data_url": "bad"}},
            )
            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "image_upload_invalid")
            self.assertEqual(payload["confidence"]["label"], "Image Upload Problem")

    def test_uploaded_turf_image_uses_image_diagnosis_path(self):
        fake_response = {
            "answer": "**Image Intake:** I treated the upload as a leaf closeup image.\n\n**Bottom Line:** This looks more like mechanical injury than disease.",
            "sources": [{"name": "Uploaded Turf Image", "type": "user_image"}],
            "confidence": {"score": 89, "label": "Image-Supported Diagnosis"},
            "needs_review": False,
            "kb_verdict": "image_diagnosis",
            "diagnostic_buckets": ["Cut quality / leaf shredding issue"],
            "advanced_science_topics": ["mower_sharpness_leaf_shredding_disease_mimic_model"],
            "image_diagnosis": {
                "image_type": "leaf closeup",
                "observed_clues": ["frayed leaf tips"],
                "diagnostic_signals": ["after mowing"],
                "field_checks": ["Inspect reels and bedknife setup."],
                "limitations": ["A photo alone cannot confirm disease."],
                "image_name": "leaf.png",
            },
            "grounding": {"verified": True, "issues": []},
        }
        with self.client as client, \
             patch("app.openai_requests_available", return_value=True), \
             patch("app.answer_image_diagnosis", return_value=fake_response):
            response = self.post(
                client,
                "/ask",
                json={
                    "question": "Does this look like mower injury?",
                    "attachment": {
                        "name": "leaf.png",
                        "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn7XWQAAAAASUVORK5CYII=",
                    },
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "image_diagnosis")
            self.assertEqual(payload["confidence"]["label"], "Image-Supported Diagnosis")
            self.assertEqual(payload["expert_router"]["selected_mode"], "image_diagnosis")
            self.assertIn("frayed leaf tips", payload["expert_router"]["matched_signals"])

            queue_response = client.get("/admin/review-queue?type=all&limit=100&offset=0")
            self.assertEqual(queue_response.status_code, 200)
            queue_payload = queue_response.get_json()
            matching = [
                item for item in queue_payload.get("items", [])
                if item.get("question") == "Does this look like mower injury?"
            ]
            self.assertTrue(matching)
            self.assertEqual(matching[0]["attachment"]["kind"], "uploaded_image")
            self.assertEqual(matching[0]["attachment"]["name"], "leaf.png")
            self.assertTrue(matching[0]["attachment"]["data_url"].startswith("data:image/png;base64,"))

    def test_supported_tank_mix_question_uses_verified_kb(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Can I tank mix Daconil and Heritage for dollar spot?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")
            self.assertEqual(payload["confidence"]["label"], "Verified Tank-Mix Guidance")

    def test_advanced_turf_science_question_uses_deterministic_layer(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "",
                        "tees": "",
                        "rough": "",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, 
                "/ask",
                json={"question": "Why do bentgrass greens lose carbohydrate reserves in heat?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_turf_science")
            self.assertEqual(payload["confidence"]["label"], "Advanced Turf Science")
            self.assertEqual(payload["advanced_science_topic"], "cool_season_heat_carbohydrate_decline")
            self.assertIn("Why it matters here", payload["answer"])
            self.assertIn("If you need a product call next", payload["answer"])

            router_events_response = client.get("/admin/expert-router-events?selected_mode=advanced_turf_science")
            self.assertEqual(router_events_response.status_code, 200)
            events = router_events_response.get_json()
            matching = [
                event for event in events
                if event["question"] == "Why do bentgrass greens lose carbohydrate reserves in heat?"
            ]
            self.assertTrue(matching)
            self.assertEqual(matching[0]["selected_mode"], "advanced_turf_science")
            self.assertEqual(matching[0]["resolved_mode"], "advanced_turf_science")
            self.assertTrue(matching[0]["used_deterministic"])
            self.assertFalse(matching[0]["needs_review"])

    def test_advanced_turf_science_route_does_not_override_product_recommendations(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "",
                        "tees": "",
                        "rough": "",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should I use for dollar spot on greens?"})
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified_surface_target_options")
            self.assertNotEqual(payload["kb_verdict"], "advanced_turf_science")

    def test_advanced_diagnosis_mode_returns_differential_framework(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, 
                "/ask",
                json={"question": "My greens are wilting even though moisture readings are high. What is causing it?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(payload["confidence"]["label"], "Advanced Diagnosis")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
            self.assertIn("Wet wilt / root oxygen limitation", payload["diagnostic_buckets"])
            self.assertIn("Field Checks To Do Today", payload["answer"])
            self.assertIn("What Not To Do Yet", payload["answer"])
            self.assertIn("If you need a product call next", payload["answer"])

    def test_advanced_diagnosis_mode_handles_pythium_vs_wet_wilt(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "",
                        "tees": "",
                        "rough": "",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, 
                "/ask",
                json={"question": "How should I diagnose Pythium root dysfunction versus wet wilt?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
            self.assertIn("Pythium/root disease complex", payload["diagnostic_buckets"])
            self.assertIn("Wet wilt / root oxygen limitation", payload["diagnostic_buckets"])
            self.assertIn("Lab Or Sample Triggers", payload["answer"])
            self.assertIn("pythium root dysfunction vs wet wilt", payload["answer"].lower())

    def test_mixed_symptom_and_product_question_prefers_diagnosis_over_product_context(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(
                client,
                "/ask",
                json={"question": "My greens are wilting. Should I spray Heritage?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["selected_mode"], "advanced_diagnosis")
            self.assertIn("Field Checks To Do Today", payload["answer"])
            self.assertNotEqual(payload["kb_verdict"], "needs_more_context")

    def test_mixed_symptom_target_and_product_question_still_prefers_diagnosis(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(
                client,
                "/ask",
                json={"question": "My bentgrass greens are wilting and spotting. Should I spray Daconil for dollar spot?"},
            )
            self.assertEqual(response.status_code, 200)

            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["selected_mode"], "advanced_diagnosis")
            self.assertIn("Field Checks To Do Today", payload["answer"])
            self.assertNotEqual(payload["kb_verdict"], "verified")

    def test_expert_router_stats_and_review_queue_are_available(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, 
                "/ask",
                json={"question": "My greens are wilting. Should I spray something?"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")

            stats_response = client.get("/admin/expert-router-stats")
            self.assertEqual(stats_response.status_code, 200)
            stats = stats_response.get_json()
            self.assertIn("total_events", stats)
            self.assertIn("deterministic_hit_rate", stats)
            self.assertIn("top_fallbacks", stats)

            events_response = client.get("/admin/expert-router-events?selected_mode=advanced_diagnosis")
            self.assertEqual(events_response.status_code, 200)
            events = events_response.get_json()
            matching = [
                event for event in events
                if event["question"] == "My greens are wilting. Should I spray something?"
            ]
            self.assertTrue(matching)
            self.assertEqual(matching[0]["selected_mode"], "advanced_diagnosis")
            self.assertEqual(matching[0]["resolved_mode"], "advanced_diagnosis")
            self.assertIn("wilting", matching[0]["matched_signals"])

    def test_kb_quality_dashboard_is_available(self):
        with self.client as client:
            response = client.get("/admin/kb-quality-dashboard")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertIn("summary", payload)
            self.assertIn("weak_fields", payload)
            self.assertIn("top_open_gaps", payload)
            self.assertIn("risky_records", payload)

    def test_eval_dashboard_is_available(self):
        with self.client as client:
            response = client.get("/admin/eval-dashboard")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertIn("summary", payload)
            self.assertIn("suites", payload)
            self.assertIn("history", payload)
            self.assertGreaterEqual(payload["summary"].get("suite_count", 0), 5)
            suite_keys = {item.get("key") for item in payload.get("suites", [])}
            self.assertTrue({"general_turf", "ambiguity", "comprehensive_100", "product_label", "image"}.issubset(suite_keys))
            self.assertTrue(payload["history"])

            cached_response = client.get("/admin/eval-dashboard")
            self.assertEqual(cached_response.status_code, 200)
            cached_payload = cached_response.get_json()
            self.assertTrue(cached_payload["summary"].get("cached"))

    def test_public_admin_allows_get_and_post_without_login(self):
        with patch.object(Config, "ALLOW_PUBLIC_ADMIN", True), patch("app.Config.ALLOW_PUBLIC_ADMIN", True):
            self.current_account_patcher.stop()
            client = app.test_client()
            with client.session_transaction() as session:
                session.clear()
            get_response = client.get("/admin/eval-dashboard")
            self.assertEqual(get_response.status_code, 200)

            with client.session_transaction() as session:
                session["_csrf_token"] = "public-admin-csrf"
            post_response = client.post(
                "/admin/course-profile",
                json={"csrf_token": "public-admin-csrf", "region": "No auth"},
            )
            self.assertEqual(post_response.status_code, 200)
            payload = post_response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["profile"]["region"], "No auth")
            self.current_account_patcher.start()

    def test_demo_mode_allows_admin_without_login(self):
        with patch.object(Config, "DEMO_MODE", True), patch("app.Config.DEMO_MODE", True):
            self.current_account_patcher.stop()
            client = app.test_client()
            with client.session_transaction() as session:
                session.clear()
            get_response = client.get("/admin/eval-dashboard")
            self.assertEqual(get_response.status_code, 200)

            with client.session_transaction() as session:
                session["_csrf_token"] = "demo-admin-csrf"
            post_response = client.post(
                "/admin/course-profile",
                json={"csrf_token": "demo-admin-csrf", "region": "Demo mode"},
            )
            self.assertEqual(post_response.status_code, 200)
            payload = post_response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["profile"]["region"], "Demo mode")
            self.current_account_patcher.start()

    def test_demo_mode_shows_admin_link_on_public_resources_page(self):
        with patch.object(Config, "DEMO_MODE", True), patch("app.Config.DEMO_MODE", True):
            self.current_account_patcher.stop()
            client = app.test_client()
            with client.session_transaction() as session:
                session.clear()
            response = client.get("/resources")
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn('href="/admin"', html)
            self.current_account_patcher.start()

    def test_admin_dashboard_includes_question_lab_and_kb_product_filter(self):
        with self.client as client:
            response = client.get("/admin")
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("Question Lab", html)
            self.assertIn('id="adminQuestionInput"', html)
            self.assertIn('id="kbGapProduct"', html)

    def test_demo_mode_cached_answers_keep_standard_response_schema(self):
        with patch.object(Config, "DEMO_MODE", True), patch("app.Config.DEMO_MODE", True):
            response = self.post(self.client, "/ask", json={"question": "How do I calibrate a boom sprayer?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "demo_cached_response")
            self.assertTrue(payload["demo_cached"])
            self.assertIn("confidence", payload)
            self.assertIn("sources", payload)
            self.assertEqual(payload["expert_router"]["selected_mode"], "demo_cached_response")

    def test_demo_mode_does_not_override_advanced_diagnosis_routing(self):
        with patch.object(Config, "DEMO_MODE", True), patch("app.Config.DEMO_MODE", True):
            save_response = self.post(
                self.client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(
                self.client,
                "/ask",
                json={
                    "question": "Could this nematode assay explain the root decline before we change the program?"
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
            self.assertIn("Nematode sampling / interpretation issue", payload["diagnostic_buckets"])

    def test_config_accepts_flask_env_as_app_env_alias(self):
        import importlib
        import config as config_module

        with patch.dict(os.environ, {"FLASK_ENV": "production"}, clear=True):
            reloaded = importlib.reload(config_module)
            self.assertEqual(reloaded.Config.APP_ENV, "production")

        importlib.reload(config_module)

    def test_kb_regression_creation_deduplicates_same_gap_question(self):
        gap_id = save_kb_gap(
            question="What should I use for Poa trivialis on greens?",
            kb_verdict="no_verified_recommendation",
            notes="test gap",
        )
        first = create_kb_regression_test(gap_id)
        second = create_kb_regression_test(gap_id)
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second.get("deduplicated"))

    def test_kb_quality_dashboard_filters_stale_gap_from_top_open_queue(self):
        save_kb_gap(
            question="What is Headway used for?",
            kb_verdict="not_verified",
            product="Headway",
            notes="legacy stale gap",
        )
        with self.client as client:
            response = client.get("/admin/kb-quality-dashboard")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            top_questions = [item["question"] for item in payload.get("top_open_gaps", [])]
            stale_questions = [item["question"] for item in payload.get("stale_open_gaps", [])]
            self.assertNotIn("What is Headway used for?", top_questions)
            self.assertIn("What is Headway used for?", stale_questions)

    def test_verified_answer_retires_matching_open_kb_gap(self):
        question = "What is Headway used for?"
        save_kb_gap(
            question=question,
            kb_verdict="not_verified",
            product="Headway",
            notes="legacy open gap that should retire after verified handling",
        )

        with self.client as client:
            response = self.post(client, "/ask", json={"question": question})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified")

            gaps_response = client.get("/admin/kb-gaps?status=open")
            self.assertEqual(gaps_response.status_code, 200)
            open_gaps = gaps_response.get_json()
            self.assertFalse(any(item["question"] == question for item in open_gaps))

            resolved_response = client.get("/admin/kb-gaps?status=resolved&product=Headway&limit=200")
            self.assertEqual(resolved_response.status_code, 200)
            resolved_gaps = resolved_response.get_json()
            matching = [item for item in resolved_gaps if item["question"] == question]
            self.assertTrue(matching)
            self.assertIn("Retired automatically", matching[0].get("notes") or "")

    def test_router_event_can_be_marked_reviewed_from_admin(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            question = "What should I use for dollar spot on greens?"
            response = self.post(client, "/ask", json={"question": question})
            self.assertEqual(response.status_code, 200)

            events_response = client.get("/admin/expert-router-events?selected_mode=verified_product")
            self.assertEqual(events_response.status_code, 200)
            events = events_response.get_json()
            event = next(event for event in events if event["question"] == question)

            review_response = self.post(client, 
                f"/admin/expert-router-events/{event['id']}/review",
                json={"needs_review": True, "notes": "manual review for testing"},
            )
            self.assertEqual(review_response.status_code, 200)
            self.assertTrue(review_response.get_json()["success"])

            flagged_response = client.get("/admin/expert-router-events?needs_review=true&selected_mode=verified_product")
            self.assertEqual(flagged_response.status_code, 200)
            flagged_events = flagged_response.get_json()
            self.assertTrue(any(item["id"] == event["id"] for item in flagged_events))

    def test_known_unsupported_surface_target_does_not_raise_router_review(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            question = "What should I use for Poa trivialis on greens?"
            response = self.post(client, "/ask", json={"question": question})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified_surface_target_options")
            self.assertIn("PoaCure", payload["answer"])
            self.assertIn("roughstalk bluegrass", payload["answer"].lower())

            events_response = client.get("/admin/expert-router-events?selected_mode=verified_product")
            self.assertEqual(events_response.status_code, 200)
            events = events_response.get_json()
            event = next(event for event in events if event["question"] == question)
            self.assertFalse(event["needs_review"])
            self.assertIsNone(event["improvement_suggestion"])

    def test_verified_product_not_verified_guardrail_does_not_raise_router_review(self):
        with self.client as client:
            question = "Can I use Xzemplar for anthracnose?"
            response = self.post(client, "/ask", json={"question": question})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "not_verified")
            self.assertFalse(payload["needs_review"])

            events_response = client.get("/admin/expert-router-events?selected_mode=verified_product")
            self.assertEqual(events_response.status_code, 200)
            events = events_response.get_json()
            event = next(event for event in events if event["question"] == question)
            self.assertFalse(event["needs_review"])

    def test_verified_product_surface_restriction_guardrail_does_not_raise_router_review(self):
        with self.client as client:
            question = "Can I use Q4 Plus on bentgrass greens for goosegrass?"
            response = self.post(client, "/ask", json={"question": question})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "surface_restricted")
            self.assertFalse(payload["needs_review"])

            events_response = client.get("/admin/expert-router-events?selected_mode=verified_product")
            self.assertEqual(events_response.status_code, 200)
            events = events_response.get_json()
            event = next(event for event in events if event["question"] == question)
            self.assertFalse(event["needs_review"])

    def test_router_event_suggests_diagnosis_topic_for_general_fallthrough(self):
        question = "Why are my greens wilting even though moisture readings are high?"
        event_id = save_expert_router_event(
            question=question,
            selected_mode="advanced_diagnosis",
            resolved_mode="general",
            attempted_modes=["advanced_diagnosis", "general"],
            fallback_mode="advanced_turf_science",
            router_confidence=0.72,
            matched_signals=["wilting", "moisture readings are high"],
            scores={"advanced_diagnosis": 12, "advanced_turf_science": 6, "verified_product": 0},
            response_kb_verdict=None,
            used_deterministic=False,
            needs_review=True,
            notes="Synthetic router miss for testing",
        )
        self.assertIsNotNone(event_id)

        with self.client as client:
            events_response = client.get("/admin/expert-router-events?needs_review=true&selected_mode=advanced_diagnosis")
            self.assertEqual(events_response.status_code, 200)
            events = events_response.get_json()
            event = next(item for item in events if item["id"] == event_id)
            suggestion = event["improvement_suggestion"]
            self.assertEqual(suggestion["type"], "diagnosis_topic")
            self.assertIn("Wet wilt / root oxygen limitation", suggestion["summary"])

    def test_router_backlog_groups_repeated_patterns(self):
        save_expert_router_event(
            question="Why are my greens wilting even though moisture readings are high after rain?",
            selected_mode="advanced_diagnosis",
            resolved_mode="general",
            attempted_modes=["advanced_diagnosis", "general"],
            fallback_mode="advanced_turf_science",
            router_confidence=0.74,
            matched_signals=["wilting", "moisture readings are high"],
            scores={"advanced_diagnosis": 13, "advanced_turf_science": 5, "verified_product": 0},
            response_kb_verdict=None,
            used_deterministic=False,
            needs_review=True,
            notes="Synthetic grouped miss A",
        )
        save_expert_router_event(
            question="Why are bentgrass greens wilting even though moisture readings are high in low spots?",
            selected_mode="advanced_diagnosis",
            resolved_mode="general",
            attempted_modes=["advanced_diagnosis", "general"],
            fallback_mode="advanced_turf_science",
            router_confidence=0.75,
            matched_signals=["wilting", "moisture readings are high", "low spots"],
            scores={"advanced_diagnosis": 14, "advanced_turf_science": 6, "verified_product": 0},
            response_kb_verdict=None,
            used_deterministic=False,
            needs_review=True,
            notes="Synthetic grouped miss B",
        )

        with self.client as client:
            backlog_response = client.get("/admin/expert-router-backlog?limit=10")
            self.assertEqual(backlog_response.status_code, 200)
            backlog = backlog_response.get_json()
            matching = [
                item for item in backlog
                if item["type"] == "diagnosis_topic"
                and "Wet wilt / root oxygen limitation" in (item.get("summary") or "")
            ]
            self.assertTrue(matching)
            self.assertGreaterEqual(matching[0]["count"], 2)
            self.assertTrue(matching[0]["sample_questions"])

    def test_router_backlog_pattern_can_create_and_update_work_item(self):
        save_expert_router_event(
            question="Why are my greens wilting even though moisture readings are high during humid nights?",
            selected_mode="advanced_diagnosis",
            resolved_mode="general",
            attempted_modes=["advanced_diagnosis", "general"],
            fallback_mode="advanced_turf_science",
            router_confidence=0.73,
            matched_signals=["wilting", "moisture readings are high"],
            scores={"advanced_diagnosis": 12, "advanced_turf_science": 5, "verified_product": 0},
            response_kb_verdict=None,
            used_deterministic=False,
            needs_review=True,
            notes="Synthetic work item seed",
        )

        with self.client as client:
            backlog_response = client.get("/admin/expert-router-backlog?limit=10")
            self.assertEqual(backlog_response.status_code, 200)
            backlog = backlog_response.get_json()
            pattern = next(
                item for item in backlog
                if item["type"] == "diagnosis_topic"
                and "Wet wilt / root oxygen limitation" in (item.get("summary") or "")
            )

            create_response = self.post(client, 
                "/admin/expert-router-backlog/work-items",
                json={"pattern_key": pattern["pattern_key"], "notes": "create from test"},
            )
            self.assertEqual(create_response.status_code, 200)
            created = create_response.get_json()
            self.assertTrue(created["success"])

            work_items_response = client.get("/admin/expert-router-work-items?status=all")
            self.assertEqual(work_items_response.status_code, 200)
            work_items = work_items_response.get_json()
            work_item = next(item for item in work_items if item["pattern_key"] == pattern["pattern_key"])
            self.assertEqual(work_item["suggestion_type"], "diagnosis_topic")

            draft_response = self.post(client, 
                f"/admin/expert-router-work-items/{work_item['id']}/generate-draft",
                json={"reviewer": "test"},
            )
            self.assertEqual(draft_response.status_code, 200)
            draft_payload = draft_response.get_json()
            self.assertTrue(draft_payload["success"])
            self.assertEqual(draft_payload["draft_type"], "diagnosis_note")
            self.assertIn("implementation_outline", draft_payload["draft_payload"])

            update_response = self.post(client, 
                f"/admin/expert-router-work-items/{work_item['id']}/status",
                json={"status": "in_progress", "notes": "started from test"},
            )
            self.assertEqual(update_response.status_code, 200)
            updated = update_response.get_json()
            self.assertTrue(updated["success"])
            self.assertEqual(updated["status"], "in_progress")

    def test_kb_gap_router_work_item_generates_candidate_draft(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            save_kb_gap(
                question="What should I use for goosegrass on greens?",
                kb_verdict="no_verified_recommendation",
                target="goosegrass",
                surface="greens",
                turf="creeping bentgrass",
                notes="synthetic open KB gap for work-item draft test",
            )
            save_expert_router_event(
                question="What should I use for goosegrass on greens?",
                selected_mode="verified_product",
                resolved_mode="verified_product",
                attempted_modes=["verified_product"],
                fallback_mode="general",
                router_confidence=0.91,
                matched_signals=["what should i use", "goosegrass", "greens"],
                scores={"verified_product": 12, "advanced_diagnosis": 0, "advanced_turf_science": 0},
                response_kb_verdict="no_verified_recommendation",
                used_deterministic=True,
                needs_review=True,
                notes="synthetic router event for work-item draft test",
            )

            backlog_response = client.get("/admin/expert-router-backlog?limit=10")
            self.assertEqual(backlog_response.status_code, 200)
            backlog = backlog_response.get_json()
            pattern = next(
                item for item in backlog
                if item["type"] == "kb_gap" and "goosegrass" in (item.get("summary") or "").lower()
            )

            create_response = self.post(client, 
                "/admin/expert-router-backlog/work-items",
                json={"pattern_key": pattern["pattern_key"], "notes": "kb gap draft from test"},
            )
            self.assertEqual(create_response.status_code, 200)
            work_item_id = create_response.get_json()["id"]

            draft_response = self.post(client, 
                f"/admin/expert-router-work-items/{work_item_id}/generate-draft",
                json={"reviewer": "test"},
            )
            self.assertEqual(draft_response.status_code, 200)
            draft = draft_response.get_json()
            self.assertTrue(draft["success"])
            self.assertEqual(draft["draft_type"], "kb_candidate")
            self.assertIsNotNone(draft["linked_candidate_id"])
            self.assertIn("candidate_patch", draft["draft_payload"])

    def test_expert_router_work_items_open_filter_hides_done_items(self):
        save_expert_router_event(
            question="Why are my greens wilting even though moisture readings are high after rain?",
            selected_mode="advanced_diagnosis",
            resolved_mode="general",
            attempted_modes=["advanced_diagnosis", "general"],
            fallback_mode="advanced_turf_science",
            router_confidence=0.74,
            matched_signals=["wilting", "moisture readings are high"],
            scores={"advanced_diagnosis": 13, "advanced_turf_science": 5, "verified_product": 0},
            response_kb_verdict=None,
            used_deterministic=False,
            needs_review=True,
            notes="Synthetic open-filter seed",
        )

        with self.client as client:
            backlog = client.get("/admin/expert-router-backlog?limit=10").get_json()
            pattern = next(
                item for item in backlog
                if item["type"] == "diagnosis_topic"
                and "Wet wilt / root oxygen limitation" in (item.get("summary") or "")
            )

            create_response = self.post(
                client,
                "/admin/expert-router-backlog/work-items",
                json={"pattern_key": pattern["pattern_key"], "notes": "open-filter test"},
            )
            self.assertEqual(create_response.status_code, 200)
            work_item_id = create_response.get_json()["id"]

            reopen_response = self.post(
                client,
                f"/admin/expert-router-work-items/{work_item_id}/status",
                json={"status": "in_progress", "notes": "reopened in open-filter test"},
            )
            self.assertEqual(reopen_response.status_code, 200)

            open_response = client.get("/admin/expert-router-work-items?status=open")
            self.assertEqual(open_response.status_code, 200)
            open_items = open_response.get_json()
            self.assertTrue(any(item["id"] == work_item_id for item in open_items))

            done_response = self.post(
                client,
                f"/admin/expert-router-work-items/{work_item_id}/status",
                json={"status": "done", "notes": "completed in open-filter test"},
            )
            self.assertEqual(done_response.status_code, 200)

            refreshed_open = client.get("/admin/expert-router-work-items?status=open")
            self.assertEqual(refreshed_open.status_code, 200)
            refreshed_items = refreshed_open.get_json()
            self.assertFalse(any(item["id"] == work_item_id for item in refreshed_items))

    def test_advanced_turf_science_audit_gap_questions_now_trigger_directly(self):
        questions = {
            "When is syringing helpful versus harmful?": "et_deficit_irrigation_syringing",
            "How should I think about nitrogen form and release rate in summer?": "nitrogen_form_release_growth_stress_balance",
            "How do wetting agent chemistry types differ?": "wetting_agent_chemistry_functional_groups",
            "How do bicarbonates and alkalinity affect micronutrients?": "bicarbonate_alkalinity_micronutrient_lockout",
            "How do growing degree days help with PGR timing?": "gdd_growth_potential_pgr_timing",
            "Why does anthracnose basal rot get worse on stressed Poa greens?": "anthracnose_basal_rot_stress_complex",
            "How should I think about reclaimed water nutrient credit and salt balance?": "reclaimed_water_nutrient_credit_salt_balance",
            "When does gypsum actually help with SAR and sodium dispersion?": "gypsum_sar_dispersion_decision_logic",
            "How should I interpret a nematode assay report on stressed greens?": "nematode_lab_interpretation_threshold_context",
            "How does herbicide carryover create transition failure after reseeding?": "herbicide_carryover_residual_transition_risk",
            "What is the greens conditioning budget for tournament prep?": "tournament_greens_stress_budget_model",
            "How should I think about ABW timing and thresholds on Poa-heavy turf?": "annual_bluegrass_weevil_lifecycle_threshold_timing",
            "How should I think about species fit for this surface and region?": "species_fit_surface_region_tradeoff_model",
            "How do temperature, moisture, and oxygen interact during seedling establishment?": "seedling_establishment_temperature_moisture_oxygen_balance",
            "Does cultivar diversity help buffer disease and stress risk?": "cultivar_diversity_stress_disease_buffering",
            "How do nozzle pressure and sprayer coverage affect canopy deposition?": "sprayer_coverage_nozzle_pressure_canopy_deposition",
            "How does rolling frequency stack mechanical stress on greens?": "roller_frequency_mechanical_stress_budget",
            "How should I interpret CEC and base saturation on a soil test?": "soil_test_cec_base_saturation_practical_limits",
            "How do spray water pH, hardness, and adjuvant fit affect performance?": "spray_water_ph_hardness_adjuvant_interaction_model",
            "How does mower sharpness and leaf shredding mimic disease?": "mower_sharpness_leaf_shredding_disease_mimic_model",
            "How does topdressing consistency affect organic matter dilution and layering drift?": "topdressing_organic_matter_dilution_layering_drift",
        }
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            for question, expected_topic in questions.items():
                with self.subTest(question=question):
                    response = self.post(client, "/ask", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["kb_verdict"], "advanced_turf_science")
                    self.assertEqual(payload["expert_router"]["mode"], "advanced_turf_science")
                    self.assertEqual(payload["advanced_science_topic"], expected_topic)
                    self.assertIn("If you need a product call next", payload["answer"])

    def test_advanced_diagnosis_mode_catches_symptom_style_audit_questions(self):
        questions = {
            "Why are my bentgrass greens wilting even though moisture readings are high?": "Wet wilt / root oxygen limitation",
            "Why are my greens wilting even though moisture readings are high after rain?": "Wet wilt / root oxygen limitation",
            "Why are bentgrass greens wilting even though moisture readings are high in low spots?": "Wet wilt / root oxygen limitation",
            "Why are my greens wilting even though moisture readings are high during humid nights?": "Wet wilt / root oxygen limitation",
            "Why did dollar spot explode after a humid week?": "Disease-favorable microclimate",
            "Why do shaded greens thin even when fertility is good?": "Shade / low-light carbon limitation",
            "Why is our zoysia so slow to green up this spring?": "Warm-season slow green-up / recovery lag",
            "Could reclaimed water chemistry be causing this stress pattern?": "Water-quality chemistry stress",
            "Could this be herbicide carryover from the residual program?": "Herbicide carryover / transition risk",
            "Could this nematode assay explain the root decline before we change the program?": "Nematode sampling / interpretation issue",
            "Could this thinning and animal digging be grub damage instead of drought?": "Insect feeding pattern / life-stage issue",
            "Is this really a species-fit problem instead of another rescue program?": "Species fit / renovation decision",
            "Our ryegrass is hanging on too long and bermuda transition is stuck. What is causing it?": "Overseed transition / bermuda competition",
            "Germination looked fine but now the seedlings are dying. What is causing it?": "Seedling establishment failure stack",
            "Why does the pattern line up with spray passes and nozzle overlap?": "Application pattern / coverage issue",
            "Why are greens getting beat up after repeated rolling and tournament prep stress?": "Mechanical stress budget overload",
            "Why do frayed leaf tips after mowing look like disease?": "Cut quality / leaf shredding issue",
            "Could this layering after topdressing be a sand compatibility issue?": "Topdressing program drift / layering issue",
        }
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            for question, expected_bucket in questions.items():
                with self.subTest(question=question):
                    response = self.post(client, "/ask", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
                    self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
                    self.assertIn(expected_bucket, payload["diagnostic_buckets"])
                    self.assertIn("Field Checks To Do Today", payload["answer"])

    def test_poa_vs_bentgrass_summer_decline_explainer_now_prefers_science_mode(self):
        with self.client as client:
            save_response = self.post(client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What causes Poa annua to decline faster than bentgrass in summer?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_turf_science")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_turf_science")
            self.assertEqual(payload["advanced_science_topic"], "poa_annua_vs_bentgrass_summer_decline")

    def test_phd_primo_timing_explainer_now_prefers_science_mode(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Why does clipping yield matter more than calendar interval in Primo timing?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_turf_science")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_turf_science")
            self.assertEqual(payload["advanced_science_topic"], "pgr_growth_suppression_thermal_rebound")

    def test_phd_water_stress_vs_disease_walkthrough_keeps_water_bucket(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Walk me through how you would separate water stress from disease on greens before spraying."})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
            self.assertIn("Wet wilt / root oxygen limitation", payload["diagnostic_buckets"])
            self.assertIn("Disease-favorable microclimate", payload["diagnostic_buckets"])

    def test_diagnosis_bucket_noise_is_reduced_for_grub_and_species_fit_questions(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            grub_response = self.post(client, "/ask", json={"question": "Could this thinning and animal digging be grub damage instead of drought?"})
            self.assertEqual(grub_response.status_code, 200)
            grub_payload = grub_response.get_json()
            self.assertEqual(grub_payload["kb_verdict"], "advanced_diagnosis")
            self.assertEqual(grub_payload["diagnostic_buckets"], ["Insect feeding pattern / life-stage issue"])

            fit_response = self.post(client, "/ask", json={"question": "Is this really a species-fit problem instead of another rescue program?"})
            self.assertEqual(fit_response.status_code, 200)
            fit_payload = fit_response.get_json()
            self.assertEqual(fit_payload["kb_verdict"], "advanced_diagnosis")
            self.assertIn("Species fit / renovation decision", fit_payload["diagnostic_buckets"])
            self.assertLessEqual(len(fit_payload["diagnostic_buckets"]), 2)

    def test_general_turf_question_routing_audit_edge_cases(self):
        with self.client as client:
            save_response = self.post(client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            science_cases = {
                "What causes bentgrass to decline in summer?": "cool_season_heat_carbohydrate_decline",
                "What causes Poa annua to decline faster than bentgrass in summer?": "poa_annua_vs_bentgrass_summer_decline",
                "What does high clip volume mean on greens?": "pgr_growth_suppression_thermal_rebound",
                "What should I know about ABW timing on Poa fairways?": "annual_bluegrass_weevil_lifecycle_threshold_timing",
            }
            for question, expected_topic in science_cases.items():
                with self.subTest(question=question):
                    response = self.post(client, "/ask", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["kb_verdict"], "advanced_turf_science")
                    self.assertEqual(payload["expert_router"]["mode"], "advanced_turf_science")
                    self.assertEqual(payload["advanced_science_topic"], expected_topic)

            diagnosis_cases = {
                "Our ryegrass is hanging on and bermuda transition is stuck. Why?": "Overseed transition / bermuda competition",
                "How do I tell mower injury from foliar disease?": "Cut quality / leaf shredding issue",
            }
            for question, expected_bucket in diagnosis_cases.items():
                with self.subTest(question=question):
                    response = self.post(client, "/ask", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["kb_verdict"], "advanced_diagnosis")
                    self.assertEqual(payload["expert_router"]["mode"], "advanced_diagnosis")
                    self.assertIn(expected_bucket, payload["diagnostic_buckets"])

    def test_general_turf_everyday_questions_route_more_helpfully(self):
        with self.client as client:
            save_response = self.post(client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            expected = {
                "What should I be doing on bentgrass greens right now?": "Surface-Specific Priorities",
                "How do I keep greens healthy in summer?": "Surface-Specific Priorities",
                "How do I keep fairways healthy through heat?": "Surface-Specific Priorities",
                "What should I watch on Poa bent greens during humid weather?": "Profile-Based Scouting",
            }
            for question, confidence_label in expected.items():
                with self.subTest(question=question):
                    response = self.post(client, "/ask", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["confidence"]["label"], confidence_label)
                    self.assertTrue(payload.get("operational_guidance"))

            science_cases = {
                "What does healthy root depth look like on greens?": "root_respiration_oxygen_balance",
                "How should I think about moisture management on greens?": "et_deficit_irrigation_syringing",
                "Why does turf get soft and puffy?": "surface_organic_matter_physics",
                "How should I think about thatch and organic matter?": "surface_organic_matter_physics",
            }
            for question, expected_topic in science_cases.items():
                with self.subTest(question=question):
                    response = self.post(client, "/ask", json={"question": question})
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload["kb_verdict"], "advanced_turf_science")
                    self.assertEqual(payload["advanced_science_topic"], expected_topic)

            diagnosis_response = self.post(client, "/ask", json={"question": "How do I know if stress is from water or disease?"})
            self.assertEqual(diagnosis_response.status_code, 200)
            diagnosis_payload = diagnosis_response.get_json()
            self.assertEqual(diagnosis_payload["kb_verdict"], "advanced_diagnosis")
            self.assertIn("Wet wilt / root oxygen limitation", diagnosis_payload["diagnostic_buckets"])
            self.assertIn("Disease-favorable microclimate", diagnosis_payload["diagnostic_buckets"])

    def test_general_turf_guidance_mode_handles_broad_agronomy_questions(self):
        with self.client as client:
            save_response = self.post(
                client,
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "soil": "sand based greens, some low spots stay wet",
                    "surfaces": {
                        "greens": "creeping bentgrass with some Poa annua",
                        "fairways": "kentucky bluegrass",
                        "tees": "bermudagrass",
                        "rough": "tall fescue",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            response = self.post(client, "/ask", json={"question": "What should I know about turf health in general?"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "general_turf_guidance")
            self.assertEqual(payload["confidence"]["label"], "General Turf Guidance")
            self.assertTrue(payload.get("operational_guidance"))
            self.assertEqual(payload["expert_router"]["selected_mode"], "general_turf_guidance")
            self.assertIn("What matters most", payload["answer"])
            self.assertIn("The question underneath all of this is", payload["answer"])
            self.assertIn("What good operators usually do well", payload["answer"])
            self.assertIn("What not to do", payload["answer"])

    def test_bentgrass_green_seeding_prep_routes_to_general_guidance_not_safety_block(self):
        with self.client as client:
            response = self.post(client, "/ask", json={"question": "Preparations for seeding a bentgrass green"})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "general_turf_guidance")
            self.assertEqual(payload["confidence"]["label"], "General Turf Guidance")
            self.assertNotEqual(payload["kb_verdict"], "safety_blocked")
            self.assertIn("What I'd get right before seed goes down", payload["answer"])
            self.assertIn("What usually sets bentgrass establishment back", payload["answer"])

    def test_known_unsupported_surface_target_is_not_treated_as_missing_kb_gap(self):
        with self.client as client:
            save_response = self.post(client, 
                "/admin/course-profile",
                json={
                    "region": "Louisville, Kentucky transition zone",
                    "surfaces": {
                        "greens": "creeping bentgrass",
                        "fairways": "",
                        "tees": "",
                        "rough": "",
                    },
                },
            )
            self.assertEqual(save_response.status_code, 200)

            question = "What should I use for Poa trivialis on greens?"
            response = self.post(client, "/ask", json={"question": question})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["kb_verdict"], "verified_surface_target_options")
            self.assertIn("PoaCure", payload["answer"])
            self.assertIn("roughstalk bluegrass", payload["answer"].lower())

            gaps_response = client.get("/admin/kb-gaps?status=open")
            self.assertEqual(gaps_response.status_code, 200)
            gaps = gaps_response.get_json()
            self.assertFalse(any(gap["question"] == question for gap in gaps))


if __name__ == "__main__":
    unittest.main()
