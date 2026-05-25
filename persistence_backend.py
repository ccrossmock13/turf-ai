"""Helpers for optional persistence backends."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from config import Config


def persistence_backend() -> str:
    return Config.PERSISTENCE_BACKEND


def using_dynamodb() -> bool:
    return persistence_backend() == "dynamodb"


def get_dynamodb_resource():
    if not using_dynamodb():
        raise RuntimeError("DynamoDB backend is not enabled.")
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - depends on deployment env
        raise RuntimeError("boto3 is required for the DynamoDB persistence backend.") from exc
    kwargs = {}
    if Config.AWS_REGION:
        kwargs["region_name"] = Config.AWS_REGION
    return boto3.resource("dynamodb", **kwargs)


def dynamodb_table(table_name: str):
    return get_dynamodb_resource().Table(table_name)


def dynamodb_table_exists(table_name: str) -> bool:
    try:
        table = dynamodb_table(table_name)
        table.load()
        return True
    except Exception:
        return False


def dynamodb_scan_all(table, **kwargs) -> list[dict[str, Any]]:
    """Return every item from a DynamoDB scan, following pagination."""
    response = table.scan(**kwargs)
    items = list(response.get("Items", []))
    last_evaluated_key = response.get("LastEvaluatedKey")
    while last_evaluated_key:
        response = table.scan(ExclusiveStartKey=last_evaluated_key, **kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
    return [to_plain_value(item) for item in items]


def dynamodb_query_all(table, **kwargs) -> list[dict[str, Any]]:
    """Return every item from a DynamoDB query, following pagination."""
    response = table.query(**kwargs)
    items = list(response.get("Items", []))
    last_evaluated_key = response.get("LastEvaluatedKey")
    while last_evaluated_key:
        response = table.query(ExclusiveStartKey=last_evaluated_key, **kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
    return [to_plain_value(item) for item in items]


def to_plain_value(value: Any):
    if isinstance(value, list):
        return [to_plain_value(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_value(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value
