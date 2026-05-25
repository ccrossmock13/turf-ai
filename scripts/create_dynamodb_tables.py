#!/usr/bin/env python3
"""Create the DynamoDB tables needed for the optional Greenside runtime backend."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from persistence_backend import get_dynamodb_resource  # noqa: E402


TABLE_DEFINITIONS = [
    {
        "TableName": Config.DYNAMODB_ACCOUNTS_TABLE,
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
    },
    {
        "TableName": Config.DYNAMODB_ACCOUNT_TOKENS_TABLE,
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
    },
    {
        "TableName": Config.DYNAMODB_COURSE_PROFILES_TABLE,
        "KeySchema": [{"AttributeName": "profile_key", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "profile_key", "AttributeType": "S"}],
    },
    {
        "TableName": Config.DYNAMODB_CHAT_TABLE,
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
    },
    {
        "TableName": Config.DYNAMODB_RATE_LIMIT_TABLE,
        "KeySchema": [
            {"AttributeName": "bucket_key", "KeyType": "HASH"},
            {"AttributeName": "created_at", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "bucket_key", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "N"},
        ],
    },
    {
        "TableName": Config.DYNAMODB_FEEDBACK_TABLE,
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
    },
]


def main() -> int:
    dynamodb = get_dynamodb_resource()
    existing = {table.name for table in dynamodb.tables.all()}
    created = []
    for definition in TABLE_DEFINITIONS:
        name = definition["TableName"]
        if name in existing:
            print(f"exists  {name}")
            continue
        table = dynamodb.create_table(
            BillingMode="PAY_PER_REQUEST",
            **definition,
        )
        print(f"create  {name}")
        table.wait_until_exists()
        created.append(name)
    if created:
        print(f"created {len(created)} table(s)")
    else:
        print("no changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
