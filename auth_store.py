"""File-backed account store for Greenside AI.

This keeps customer accounts out of SQL while still providing:
- hashed passwords
- roles
- terms/privacy acceptance tracking
- simple multi-account isolation keys
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from datetime import timedelta
from hashlib import sha256
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from persistence_backend import dynamodb_scan_all, dynamodb_table, to_plain_value, using_dynamodb

try:  # pragma: no cover - boto3 is deployment-specific
    from boto3.dynamodb.conditions import Attr
except Exception:  # pragma: no cover
    Attr = None


DATA_DIR = os.getenv("DATA_DIR", "data")
ACCOUNTS_PATH = os.path.join(DATA_DIR, "accounts", "users.json")
PASSWORD_RESET_PATH = os.path.join(DATA_DIR, "accounts", "password_resets.json")
EMAIL_VERIFICATION_PATH = os.path.join(DATA_DIR, "accounts", "email_verifications.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store_dir() -> None:
    os.makedirs(os.path.dirname(ACCOUNTS_PATH), exist_ok=True)


def _blank_store() -> dict[str, Any]:
    return {"users": []}


def _blank_reset_store() -> dict[str, Any]:
    return {"tokens": []}


def load_account_store() -> dict[str, Any]:
    if using_dynamodb():
        table = dynamodb_table(Config.DYNAMODB_ACCOUNTS_TABLE)
        users = dynamodb_scan_all(table)
        return {"users": users}
    _ensure_store_dir()
    try:
        with open(ACCOUNTS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("users"), list):
                return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return _blank_store()


def save_account_store(store: dict[str, Any]) -> None:
    if using_dynamodb():
        table = dynamodb_table(Config.DYNAMODB_ACCOUNTS_TABLE)
        existing = load_account_store()["users"]
        incoming = {item["id"]: item for item in (store.get("users") or []) if item.get("id")}
        existing_ids = {item.get("id") for item in existing}
        for account_id in existing_ids - set(incoming):
            if account_id:
                table.delete_item(Key={"id": account_id})
        for account in incoming.values():
            table.put_item(Item=account)
        return
    _ensure_store_dir()
    with open(ACCOUNTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)


def load_password_reset_store() -> dict[str, Any]:
    if using_dynamodb():
        if Attr is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        table = dynamodb_table(Config.DYNAMODB_ACCOUNT_TOKENS_TABLE)
        tokens = dynamodb_scan_all(
            table,
            FilterExpression=Attr("token_type").eq("password_reset"),
        )
        return {"tokens": tokens}
    _ensure_store_dir()
    try:
        with open(PASSWORD_RESET_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("tokens"), list):
                return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return _blank_reset_store()


def save_password_reset_store(store: dict[str, Any]) -> None:
    if using_dynamodb():
        _save_token_store(store, token_type="password_reset")
        return
    _ensure_store_dir()
    with open(PASSWORD_RESET_PATH, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)


def load_email_verification_store() -> dict[str, Any]:
    if using_dynamodb():
        if Attr is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        table = dynamodb_table(Config.DYNAMODB_ACCOUNT_TOKENS_TABLE)
        tokens = dynamodb_scan_all(
            table,
            FilterExpression=Attr("token_type").eq("email_verification"),
        )
        return {"tokens": tokens}
    _ensure_store_dir()
    try:
        with open(EMAIL_VERIFICATION_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("tokens"), list):
                return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return _blank_reset_store()


def save_email_verification_store(store: dict[str, Any]) -> None:
    if using_dynamodb():
        _save_token_store(store, token_type="email_verification")
        return
    _ensure_store_dir()
    with open(EMAIL_VERIFICATION_PATH, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)


def _save_token_store(store: dict[str, Any], *, token_type: str) -> None:
    table = dynamodb_table(Config.DYNAMODB_ACCOUNT_TOKENS_TABLE)
    existing = load_password_reset_store()["tokens"] if token_type == "password_reset" else load_email_verification_store()["tokens"]
    existing_ids = {item.get("id") for item in existing}
    incoming = {}
    for item in store.get("tokens", []):
        if not item.get("id"):
            continue
        record = dict(item)
        record["token_type"] = token_type
        incoming[record["id"]] = record
    for token_id in existing_ids - set(incoming):
        if token_id:
            table.delete_item(Key={"id": token_id})
    for token in incoming.values():
        table.put_item(Item=token)


def list_accounts() -> list[dict[str, Any]]:
    return load_account_store()["users"]


def count_accounts() -> int:
    return len(list_accounts())


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def public_account(account: dict[str, Any] | None) -> dict[str, Any] | None:
    if not account:
        return None
    return {
        "id": account["id"],
        "email": account["email"],
        "name": account.get("name", ""),
        "organization": account.get("organization", ""),
        "role": account.get("role", "user"),
        "email_verified_at": account.get("email_verified_at"),
        "created_at": account.get("created_at"),
        "terms_accepted_at": account.get("terms_accepted_at"),
        "privacy_accepted_at": account.get("privacy_accepted_at"),
    }


def get_account_by_email(email: str) -> dict[str, Any] | None:
    normalized = _normalize_email(email)
    if not normalized:
        return None
    for account in list_accounts():
        if account.get("email") == normalized:
            return account
    return None


def get_account_by_id(account_id: str) -> dict[str, Any] | None:
    if not account_id:
        return None
    for account in list_accounts():
        if account.get("id") == account_id:
            return account
    return None


def create_account(
    email: str,
    password: str,
    *,
    name: str = "",
    organization: str = "",
    accepted_terms: bool = False,
    accepted_privacy: bool = False,
    role: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        return None, "Enter a valid email address."
    if get_account_by_email(normalized):
        return None, "An account with that email already exists."
    if len(str(password or "")) < 10:
        return None, "Password must be at least 10 characters."
    if not accepted_terms or not accepted_privacy:
        return None, "You must accept the Terms and Privacy Policy."

    store = load_account_store()
    assigned_role = role or ("admin" if not store["users"] else "user")
    now = _utc_now()
    account = {
        "id": uuid.uuid4().hex,
        "email": normalized,
        "name": str(name or "").strip(),
        "organization": str(organization or "").strip(),
        "role": assigned_role,
        "password_hash": generate_password_hash(password),
        "created_at": now,
        "email_verified_at": None,
        "terms_accepted_at": now,
        "privacy_accepted_at": now,
        "status": "active",
    }
    store["users"].append(account)
    save_account_store(store)
    return public_account(account), None


def verify_credentials(email: str, password: str) -> dict[str, Any] | None:
    account = get_account_by_email(email)
    if not account:
        return None
    if account.get("status") != "active":
        return None
    if not check_password_hash(account.get("password_hash", ""), str(password or "")):
        return None
    return public_account(account)


def mark_email_verified(account_id: str) -> dict[str, Any] | None:
    if not account_id:
        return None
    store = load_account_store()
    for account in store["users"]:
        if account.get("id") != account_id:
            continue
        account["email_verified_at"] = account.get("email_verified_at") or _utc_now()
        save_account_store(store)
        return public_account(account)
    return None


def update_account(
    account_id: str,
    *,
    name: str | None = None,
    organization: str | None = None,
    new_password: str | None = None,
    current_password: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not account_id:
        return None, "Missing account id."

    store = load_account_store()
    for account in store["users"]:
        if account.get("id") != account_id:
            continue

        if name is not None:
            account["name"] = str(name or "").strip()[:120]
        if organization is not None:
            account["organization"] = str(organization or "").strip()[:160]

        if new_password is not None and str(new_password).strip():
            if len(str(new_password or "")) < 10:
                return None, "Password must be at least 10 characters."
            if not current_password:
                return None, "Enter your current password to set a new password."
            if not check_password_hash(account.get("password_hash", ""), str(current_password or "")):
                return None, "Current password is incorrect."
            account["password_hash"] = generate_password_hash(str(new_password))

        save_account_store(store)
        return public_account(account), None

    return None, "Account not found."


def deactivate_account(account_id: str) -> tuple[dict[str, Any] | None, str | None]:
    if not account_id:
        return None, "Missing account id."
    store = load_account_store()
    for account in store["users"]:
        if account.get("id") != account_id:
            continue
        account["status"] = "disabled"
        account["disabled_at"] = _utc_now()
        save_account_store(store)
        return public_account(account), None
    return None, "Account not found."


def delete_account(account_id: str) -> tuple[dict[str, Any] | None, str | None]:
    if not account_id:
        return None, "Missing account id."

    store = load_account_store()
    removed = None
    remaining = []
    for account in store["users"]:
        if account.get("id") == account_id and removed is None:
            removed = account
            continue
        remaining.append(account)
    if removed is None:
        return None, "Account not found."

    store["users"] = remaining
    save_account_store(store)

    reset_store = load_password_reset_store()
    reset_store["tokens"] = [
        token
        for token in reset_store["tokens"]
        if token.get("account_id") != account_id and token.get("email") != removed.get("email")
    ]
    save_password_reset_store(reset_store)

    verification_store = load_email_verification_store()
    verification_store["tokens"] = [
        token
        for token in verification_store["tokens"]
        if token.get("account_id") != account_id and token.get("email") != removed.get("email")
    ]
    save_email_verification_store(verification_store)
    return public_account(removed), None


def _token_hash(token: str) -> str:
    return sha256(str(token or "").encode("utf-8")).hexdigest()


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def create_password_reset_token(email: str, *, ttl_minutes: int = 60) -> str | None:
    account = get_account_by_email(email)
    if not account:
        return None

    store = load_password_reset_store()
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)

    for item in store["tokens"]:
        if item.get("account_id") == account["id"] and not item.get("used_at"):
            item["revoked_at"] = now.isoformat()

    store["tokens"].append({
        "id": uuid.uuid4().hex,
        "account_id": account["id"],
        "email": account["email"],
        "token_hash": _token_hash(token),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
        "used_at": None,
        "revoked_at": None,
    })
    save_password_reset_store(store)
    return token


def create_email_verification_token(email: str, *, ttl_minutes: int = 1440) -> str | None:
    account = get_account_by_email(email)
    if not account:
        return None
    if account.get("email_verified_at"):
        return None

    store = load_email_verification_store()
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)

    for item in store["tokens"]:
        if item.get("account_id") == account["id"] and not item.get("used_at"):
            item["revoked_at"] = now.isoformat()

    store["tokens"].append({
        "id": uuid.uuid4().hex,
        "account_id": account["id"],
        "email": account["email"],
        "token_hash": _token_hash(token),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
        "used_at": None,
        "revoked_at": None,
    })
    save_email_verification_store(store)
    return token


def get_password_reset_account(token: str) -> dict[str, Any] | None:
    hashed = _token_hash(token)
    store = load_password_reset_store()
    now = datetime.now(timezone.utc)

    for item in store["tokens"]:
        if item.get("token_hash") != hashed:
            continue
        if item.get("used_at") or item.get("revoked_at"):
            return None
        expires_at = _parse_utc(item.get("expires_at"))
        if not expires_at or expires_at < now:
            return None
        return public_account(get_account_by_id(item.get("account_id")))
    return None


def get_email_verification_account(token: str) -> dict[str, Any] | None:
    hashed = _token_hash(token)
    store = load_email_verification_store()
    now = datetime.now(timezone.utc)

    for item in store["tokens"]:
        if item.get("token_hash") != hashed:
            continue
        if item.get("used_at") or item.get("revoked_at"):
            return None
        expires_at = _parse_utc(item.get("expires_at"))
        if not expires_at or expires_at < now:
            return None
        return public_account(get_account_by_id(item.get("account_id")))
    return None


def consume_password_reset_token(token: str, new_password: str) -> tuple[dict[str, Any] | None, str | None]:
    if len(str(new_password or "")) < 10:
        return None, "Password must be at least 10 characters."

    hashed = _token_hash(token)
    reset_store = load_password_reset_store()
    now = datetime.now(timezone.utc)

    for item in reset_store["tokens"]:
        if item.get("token_hash") != hashed:
            continue
        if item.get("used_at") or item.get("revoked_at"):
            return None, "That reset link is no longer valid."
        expires_at = _parse_utc(item.get("expires_at"))
        if not expires_at or expires_at < now:
            return None, "That reset link has expired."

        account_id = item.get("account_id")
        account_store = load_account_store()
        for account in account_store["users"]:
            if account.get("id") != account_id:
                continue
            account["password_hash"] = generate_password_hash(str(new_password))
            save_account_store(account_store)
            item["used_at"] = now.isoformat()
            save_password_reset_store(reset_store)
            return public_account(account), None
        return None, "Account not found."

    return None, "That reset link is not valid."


def consume_email_verification_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    hashed = _token_hash(token)
    verification_store = load_email_verification_store()
    now = datetime.now(timezone.utc)

    for item in verification_store["tokens"]:
        if item.get("token_hash") != hashed:
            continue
        if item.get("used_at") or item.get("revoked_at"):
            return None, "That verification link is no longer valid."
        expires_at = _parse_utc(item.get("expires_at"))
        if not expires_at or expires_at < now:
            return None, "That verification link has expired."

        account = mark_email_verified(item.get("account_id"))
        if not account:
            return None, "Account not found."
        item["used_at"] = now.isoformat()
        save_email_verification_store(verification_store)
        return account, None

    return None, "That verification link is not valid."
