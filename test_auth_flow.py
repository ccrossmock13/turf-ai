import unittest
import os
import tempfile
from unittest.mock import patch

import auth_store
import chat_history
from app import RATE_LIMIT_BUCKETS, app, Config
from chat_history import create_session, export_account_conversations, save_message
from course_profile import load_course_profile


class AuthFlowTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.temp_dir = tempfile.TemporaryDirectory(prefix="greenside-auth-")
        self.data_dir_patcher = patch.dict(os.environ, {"DATA_DIR": self.temp_dir.name})
        self.accounts_path_patcher = patch("auth_store.ACCOUNTS_PATH", os.path.join(self.temp_dir.name, "accounts", "users.json"))
        self.password_resets_path_patcher = patch("auth_store.PASSWORD_RESET_PATH", os.path.join(self.temp_dir.name, "accounts", "password_resets.json"))
        self.email_verifications_path_patcher = patch("auth_store.EMAIL_VERIFICATION_PATH", os.path.join(self.temp_dir.name, "accounts", "email_verifications.json"))
        self.chat_db_path_patcher = patch("chat_history.DB_PATH", os.path.join(self.temp_dir.name, "greenside_conversations.db"))
        self.require_email_verification_patcher = patch.object(Config, "REQUIRE_EMAIL_VERIFICATION", False)
        self.require_email_verification_app_patcher = patch("app.Config.REQUIRE_EMAIL_VERIFICATION", False)
        self.allow_public_admin_patcher = patch.object(Config, "ALLOW_PUBLIC_ADMIN", False)
        self.allow_public_admin_app_patcher = patch("app.Config.ALLOW_PUBLIC_ADMIN", False)
        self.demo_mode_patcher = patch.object(Config, "DEMO_MODE", False)
        self.demo_mode_app_patcher = patch("app.Config.DEMO_MODE", False)
        self.data_dir_patcher.start()
        self.accounts_path_patcher.start()
        self.password_resets_path_patcher.start()
        self.email_verifications_path_patcher.start()
        self.chat_db_path_patcher.start()
        self.require_email_verification_patcher.start()
        self.require_email_verification_app_patcher.start()
        self.allow_public_admin_patcher.start()
        self.allow_public_admin_app_patcher.start()
        self.demo_mode_patcher.start()
        self.demo_mode_app_patcher.start()
        auth_store.save_account_store({"users": []})
        auth_store.save_password_reset_store({"tokens": []})
        RATE_LIMIT_BUCKETS.clear()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["_csrf_token"] = "test-csrf-token"
        self.csrf_token = "test-csrf-token"

    def tearDown(self):
        if hasattr(self, "chat_db_path_patcher"):
            self.chat_db_path_patcher.stop()
        if hasattr(self, "email_verifications_path_patcher"):
            self.email_verifications_path_patcher.stop()
        if hasattr(self, "password_resets_path_patcher"):
            self.password_resets_path_patcher.stop()
        if hasattr(self, "accounts_path_patcher"):
            self.accounts_path_patcher.stop()
        if hasattr(self, "data_dir_patcher"):
            self.data_dir_patcher.stop()
        if hasattr(self, "allow_public_admin_app_patcher"):
            self.allow_public_admin_app_patcher.stop()
        if hasattr(self, "allow_public_admin_patcher"):
            self.allow_public_admin_patcher.stop()
        if hasattr(self, "demo_mode_app_patcher"):
            self.demo_mode_app_patcher.stop()
        if hasattr(self, "demo_mode_patcher"):
            self.demo_mode_patcher.stop()
        if hasattr(self, "require_email_verification_app_patcher"):
            self.require_email_verification_app_patcher.stop()
        if hasattr(self, "require_email_verification_patcher"):
            self.require_email_verification_patcher.stop()
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def _csrf_token(self):
        return self.csrf_token

    def _refresh_csrf_token(self):
        with self.client.session_transaction() as session:
            self.csrf_token = session.get("_csrf_token", self.csrf_token)
        return self.csrf_token

    def post_json(self, path, payload):
        body = dict(payload)
        body.setdefault("csrf_token", self.csrf_token)
        response = self.client.post(path, json=body)
        self._refresh_csrf_token()
        return response

    def post_form(self, path, payload):
        body = dict(payload)
        body.setdefault("_csrf_token", self.csrf_token)
        response = self.client.post(path, data=body)
        self._refresh_csrf_token()
        return response

    def test_admin_route_requires_login(self):
        with patch.object(Config, "ALLOW_PUBLIC_ADMIN", False), patch("app.Config.ALLOW_PUBLIC_ADMIN", False):
            response = self.client.get("/admin")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.location)

    def test_dynamodb_account_store_uses_paginated_scan_helper(self):
        fake_table = object()
        expected_users = [{"id": "acct-1", "email": "owner@example.com"}]
        with patch("auth_store.using_dynamodb", return_value=True), \
             patch("auth_store.dynamodb_table", return_value=fake_table), \
             patch("auth_store.dynamodb_scan_all", return_value=expected_users) as scan_all:
            store = auth_store.load_account_store()

        self.assertEqual(store, {"users": expected_users})
        scan_all.assert_called_once_with(fake_table)

    def test_dynamodb_password_reset_store_uses_paginated_scan_helper(self):
        class FakeAttrBuilder:
            def __init__(self, name):
                self.name = name

            def eq(self, value):
                return (self.name, value)

        fake_table = object()
        expected_tokens = [{"id": "tok-1", "token_type": "password_reset"}]
        expected_filter = ("token_type", "password_reset")
        with patch("auth_store.using_dynamodb", return_value=True), \
             patch("auth_store.Attr", FakeAttrBuilder), \
             patch("auth_store.dynamodb_table", return_value=fake_table), \
             patch("auth_store.dynamodb_scan_all", return_value=expected_tokens) as scan_all:
            store = auth_store.load_password_reset_store()

        self.assertEqual(store, {"tokens": expected_tokens})
        scan_all.assert_called_once_with(fake_table, FilterExpression=expected_filter)

    def test_dynamodb_conversation_history_uses_paginated_query_helper(self):
        class FakeKeyCondition:
            def __init__(self, value):
                self.value = value

        class FakeKeyBuilder:
            def __init__(self, name):
                self.name = name

            def eq(self, value):
                return FakeKeyCondition((self.name, value))

        fake_table = object()
        items = [
            {"entity_type": "conversation", "timestamp": "2026-04-01T09:00:00"},
            {"entity_type": "message", "role": "user", "content": "First", "timestamp": "2026-04-01T10:00:00"},
            {"entity_type": "message", "role": "assistant", "content": "Second", "timestamp": "2026-04-01T10:01:00"},
            {"entity_type": "message", "role": "user", "content": "Third", "timestamp": "2026-04-01T10:02:00"},
        ]
        with patch("chat_history.using_dynamodb", return_value=True), \
             patch("chat_history.Key", FakeKeyBuilder), \
             patch("chat_history.dynamodb_table", return_value=fake_table), \
             patch("chat_history.dynamodb_query_all", return_value=items) as query_all:
            history = chat_history.get_conversation_history("conv-1", limit=2)

        self.assertEqual([item["content"] for item in history], ["Second", "Third"])
        query_all.assert_called_once()

    def test_dynamodb_export_account_conversations_uses_paginated_scan_helper(self):
        class FakeCondition:
            def __init__(self, value):
                self.value = value

            def __and__(self, other):
                return ("AND", self.value, other.value)

        class FakeAttrBuilder:
            def __init__(self, name):
                self.name = name

            def eq(self, value):
                return FakeCondition((self.name, value))

        fake_table = object()
        fake_filter = ("AND", ("entity_type", "conversation"), ("account_id", "acct-1"))
        conversations = [
            {
                "conversation_id": "conv-1",
                "session_id": "sess-1",
                "created_at": "2026-04-01T10:00:00",
                "last_active": "2026-04-01T10:05:00",
                "user_info": {"name": "Owner"},
            },
            {
                "conversation_id": "conv-2",
                "session_id": "sess-2",
                "created_at": "2026-04-02T10:00:00",
                "last_active": "2026-04-02T10:05:00",
                "user_info": {"name": "Owner"},
            },
        ]
        with patch("chat_history.using_dynamodb", return_value=True), \
             patch("chat_history.Attr", FakeAttrBuilder), \
             patch("chat_history.dynamodb_table", return_value=fake_table), \
             patch("chat_history.dynamodb_scan_all", return_value=conversations) as scan_all, \
             patch("chat_history.get_conversation_history", return_value=[]) as get_history:
            exported = chat_history.export_account_conversations("acct-1")

        self.assertEqual(len(exported), 2)
        scan_all.assert_called_once_with(fake_table, FilterExpression=fake_filter)
        self.assertEqual(get_history.call_count, 2)

    def test_login_error_preserves_email_field(self):
        response = self.post_form("/login", {"email": "keeper@example.com", "password": "wrong-pass"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'value="keeper@example.com"', response.data)

    def test_register_error_preserves_entered_fields(self):
        response = self.post_form(
            "/register",
            {
                "name": "Owner",
                "organization": "Club",
                "email": "owner@example.com",
                "password": "short",
                "accept_terms": "true",
                "accept_privacy": "true",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'value="Owner"', response.data)
        self.assertIn(b'value="Club"', response.data)
        self.assertIn(b'value="owner@example.com"', response.data)

    def test_register_login_and_new_session_preserves_auth(self):
        register = self.post_json(
            "/register",
            {
                "email": "owner@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        payload = register.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["account"]["role"], "admin")

        with self.client.session_transaction() as session:
            self.assertEqual(session.get("account_email"), "owner@example.com")
            self.assertEqual(session.get("account_role"), "admin")

        account_page = self.client.get("/account")
        self.assertEqual(account_page.status_code, 200)

        reset = self.post_json("/api/new-session", {})
        self.assertEqual(reset.status_code, 200)

        still_signed_in = self.client.get("/account")
        self.assertEqual(still_signed_in.status_code, 200)

    def test_non_admin_is_blocked_from_admin_routes(self):
        auth_store.create_account(
            "admin2@example.com",
            "StrongPass123!",
            accepted_terms=True,
            accepted_privacy=True,
            role="admin",
        )
        auth_store.create_account(
            "user@example.com",
            "StrongPass123!",
            accepted_terms=True,
            accepted_privacy=True,
            role="user",
        )
        login = self.post_json("/login", {"email": "user@example.com", "password": "StrongPass123!"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["success"])

        with patch.object(Config, "ALLOW_PUBLIC_ADMIN", False), patch("app.Config.ALLOW_PUBLIC_ADMIN", False):
            blocked = self.client.get("/admin/stats")
            self.assertEqual(blocked.status_code, 403)

    def test_account_settings_can_update_name_and_password(self):
        register = self.post_json(
            "/register",
            {
                "email": "owner@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        login = self.post_json("/login", {"email": "owner@example.com", "password": "StrongPass123!"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["success"])

        update = self.post_json(
            "/account",
            {
                "name": "Course Owner",
                "organization": "Better Club",
                "current_password": "StrongPass123!",
                "new_password": "EvenStronger456!",
            },
        )
        self.assertEqual(update.status_code, 200)
        payload = update.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["account"]["name"], "Course Owner")
        self.assertEqual(payload["account"]["organization"], "Better Club")

        logout = self.post_json("/logout", {})
        self.assertEqual(logout.status_code, 200)

        login = self.post_json("/login", {"email": "owner@example.com", "password": "EvenStronger456!"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["success"])

    def test_account_settings_can_update_core_course_profile(self):
        register = self.post_json(
            "/register",
            {
                "email": "owner@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)

        update = self.post_json(
            "/account",
            {
                "region": "Louisville, Kentucky transition zone",
                "soil": "Sand-based greens",
                "greens_surface": "Creeping bentgrass",
                "fairways_surface": "Bermudagrass",
                "greens_mowing_height": "0.125 inches",
                "preferred_products": "Heritage, Daconil",
                "course_notes": "Recurring pressure: dollar spot; low wet area behind 7 green",
            },
        )
        self.assertEqual(update.status_code, 200)
        payload = update.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["profile"]["region"], "Louisville, Kentucky transition zone")
        self.assertEqual(payload["profile"]["soil"], "Sand-based greens")
        self.assertEqual(payload["profile"]["surfaces"]["greens"], "Creeping bentgrass")
        self.assertEqual(payload["profile"]["surfaces"]["fairways"], "Bermudagrass")
        self.assertEqual(payload["profile"]["mowing_heights"]["greens"], "0.125 inches")
        self.assertIn("Heritage", payload["profile"]["preferred_products"])
        self.assertGreater(payload["profile_health"]["score"], 0)

    def test_post_without_csrf_is_rejected(self):
        response = self.client.post("/login", json={"email": "user@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("security check failed", response.get_json()["error"].lower())

    def test_password_reset_flow_works_in_development_json(self):
        register = self.post_json(
            "/register",
            {
                "email": "owner@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)

        request_reset = self.post_json("/forgot-password", {"email": "owner@example.com"})
        self.assertEqual(request_reset.status_code, 200)
        payload = request_reset.get_json()
        self.assertIn("reset_url", payload)
        token = payload["reset_url"].rsplit("/", 1)[-1]

        reset = self.post_json(
            f"/reset-password/{token}",
            {
                "new_password": "EvenStronger456!",
                "confirm_password": "EvenStronger456!",
            },
        )
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.get_json()["success"])

        logout = self.post_json("/logout", {})
        self.assertEqual(logout.status_code, 200)

        login = self.post_json("/login", {"email": "owner@example.com", "password": "EvenStronger456!"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.get_json()["success"])

    def test_register_returns_verification_link_in_development_json(self):
        register = self.post_json(
            "/register",
            {
                "email": "verifyme@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        payload = register.get_json()
        self.assertIn("verify_url", payload)
        self.assertFalse(payload["account"]["email_verified_at"])

    def test_verify_email_route_marks_account_verified(self):
        register = self.post_json(
            "/register",
            {
                "email": "verifyme@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        token = register.get_json()["verify_url"].rsplit("/", 1)[-1]
        response = self.client.get(f"/verify-email/{token}", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        verified = auth_store.get_account_by_email("verifyme@example.com")
        self.assertTrue(verified["email_verified_at"])

    def test_login_can_require_email_verification(self):
        register = self.post_json(
            "/register",
            {
                "email": "verifyme@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        self.post_json("/logout", {})
        with patch("app.Config.REQUIRE_EMAIL_VERIFICATION", True):
            login = self.post_json("/login", {"email": "verifyme@example.com", "password": "StrongPass123!"})
        self.assertEqual(login.status_code, 403)
        self.assertTrue(login.get_json()["requires_email_verification"])

    def test_resend_verification_returns_fresh_link(self):
        register = self.post_json(
            "/register",
            {
                "email": "verifyme@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        response = self.post_json("/resend-verification", {"email": "verifyme@example.com"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("verify_url", payload)
        self.assertIn("/verify-email/", payload["verify_url"])

    def test_register_does_not_auto_login_when_email_verification_is_required(self):
        with patch("app.Config.REQUIRE_EMAIL_VERIFICATION", True):
            register = self.post_json(
                "/register",
                {
                    "email": "verifyme@example.com",
                    "password": "StrongPass123!",
                    "name": "Owner",
                    "organization": "Club",
                    "accept_terms": True,
                    "accept_privacy": True,
                },
            )
        self.assertEqual(register.status_code, 202)
        payload = register.get_json()
        self.assertTrue(payload["requires_email_verification"])
        with patch.object(Config, "ALLOW_PUBLIC_ADMIN", False), patch("app.Config.ALLOW_PUBLIC_ADMIN", False):
            admin = self.client.get("/admin")
            self.assertEqual(admin.status_code, 302)

    def test_login_rate_limit_kicks_in(self):
        for _ in range(10):
            response = self.post_json("/login", {"email": "nobody@example.com", "password": "wrong-pass"})
            self.assertIn(response.status_code, {200, 401})

        limited = self.post_json("/login", {"email": "nobody@example.com", "password": "wrong-pass"})
        self.assertEqual(limited.status_code, 429)
        self.assertIn("retry_after", limited.get_json())

    def test_account_export_includes_profile_and_account_scoped_conversations(self):
        register = self.post_json(
            "/register",
            {
                "email": "owner@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        account = auth_store.get_account_by_email("owner@example.com")
        self.assertIsNotNone(account)

        self.post_json(
            "/account",
            {
                "region": "Louisville, Kentucky transition zone",
                "greens_surface": "Creeping bentgrass",
            },
        )
        session_id, conversation_id = create_session(account_id=account["id"], user_info={"account_id": account["id"]})
        self.assertTrue(session_id)
        save_message(conversation_id, "user", "How do I keep greens healthy in summer?")
        save_message(conversation_id, "assistant", "Watch moisture, roots, and rolling stress.")

        response = self.client.get("/account/export")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["account"]["email"], "owner@example.com")
        self.assertEqual(payload["course_profile"]["region"], "Louisville, Kentucky transition zone")
        self.assertEqual(payload["summary"]["conversation_count"], 1)
        self.assertEqual(payload["summary"]["message_count"], 2)
        self.assertIn("greens", payload["course_profile"]["surfaces"])

    def test_account_delete_removes_account_profile_and_conversations(self):
        register = self.post_json(
            "/register",
            {
                "email": "owner@example.com",
                "password": "StrongPass123!",
                "name": "Owner",
                "organization": "Club",
                "accept_terms": True,
                "accept_privacy": True,
            },
        )
        self.assertEqual(register.status_code, 200)
        account = auth_store.get_account_by_email("owner@example.com")
        self.assertIsNotNone(account)

        self.post_json(
            "/account",
            {
                "region": "Louisville, Kentucky transition zone",
                "greens_surface": "Creeping bentgrass",
            },
        )
        _, conversation_id = create_session(account_id=account["id"], user_info={"account_id": account["id"]})
        save_message(conversation_id, "user", "How do I keep greens healthy in summer?")
        save_message(conversation_id, "assistant", "Watch moisture, roots, and rolling stress.")

        delete_response = self.post_json(
            "/account/delete",
            {
                "current_password": "StrongPass123!",
                "confirm_email": "owner@example.com",
            },
        )
        self.assertEqual(delete_response.status_code, 200)
        payload = delete_response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["deleted_conversations"], 1)
        self.assertTrue(payload["deleted_course_profile"])
        self.assertIsNone(auth_store.get_account_by_email("owner@example.com"))
        self.assertEqual(export_account_conversations(account["id"]), [])
        self.assertEqual(load_course_profile(account["id"])["region"], "")

        with patch.object(Config, "ALLOW_PUBLIC_ADMIN", False), patch("app.Config.ALLOW_PUBLIC_ADMIN", False):
            admin = self.client.get("/admin")
            self.assertEqual(admin.status_code, 302)
