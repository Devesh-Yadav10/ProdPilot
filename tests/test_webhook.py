import asyncio
import hashlib
import hmac
import os
import sqlite3

import pytest
from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")

import history_store
import main


def _request(body: bytes, signature: str | None = None) -> Request:
    headers = []
    if signature:
        headers.append((b"x-hub-signature-256", signature.encode()))

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "method": "POST", "headers": headers}, receive)


def test_verify_signature_returns_the_raw_body() -> None:
    body = b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(
        main.WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    assert asyncio.run(main.verify_signature(_request(body, signature), signature)) == body


def test_verify_signature_rejects_an_invalid_signature() -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            main.verify_signature(
                _request(b"{}", "sha256=invalid"),
                "sha256=invalid",
            )
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid webhook signature"


def test_processed_delivery_is_recorded_in_sqlite(monkeypatch) -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE processed_pull_requests (
            repository TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            head_sha TEXT NOT NULL,
            processed_at TIMESTAMP NOT NULL,
            PRIMARY KEY (repository, pr_number, head_sha)
        )
        """
    )
    monkeypatch.setattr(history_store, "_processed_connection", lambda: connection)

    assert not history_store.already_processed("owner/repo", 12, "abc123")
    history_store.record_processed("owner/repo", 12, "abc123")

    assert history_store.already_processed("owner/repo", 12, "abc123")
    assert not history_store.already_processed("owner/repo", 12, "different-sha")


def test_webhook_skips_an_already_processed_pull_request(monkeypatch) -> None:
    monkeypatch.setattr(main, "already_processed", lambda *_: True)
    body = b'''{
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"number": 12, "head": {"sha": "abc123"}}
    }'''

    response = asyncio.run(main.github_webhook(body=body, x_github_event="pull_request"))

    assert response == {"status": "skipped", "reason": "already processed"}
