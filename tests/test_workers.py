import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from arcana.workers.base import BaseWorker


class EchoWorker(BaseWorker):
    async def handle(self, payload: dict) -> dict:
        return {"echo": payload}


@pytest.fixture
def worker():
    return EchoWorker(nats_url="nats://localhost:4222", subject="arcana.echo")


async def test_handle_returns_echo(worker):
    payload = {"job_id": "abc", "data": "hello"}
    result = await worker.handle(payload)
    assert result == {"echo": payload}


def test_make_idempotency_key(worker):
    key = worker.make_idempotency_key("job-1", "extract", 1)
    assert key == "job-1:extract:1"


def test_is_processed_initially_false(worker):
    assert worker.is_processed("some-key") is False


def test_mark_processed_makes_it_true(worker):
    worker.mark_processed("some-key")
    assert worker.is_processed("some-key") is True


async def test_process_msg_skips_duplicate(worker):
    worker.mark_processed("key-abc")

    msg = MagicMock()
    msg.headers = {
        "Arcana-Idempotency-Key": "key-abc",
        "Arcana-Correlation-Id": "corr-1",
    }
    msg.respond = AsyncMock()
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()

    await worker.process_msg(msg)

    msg.respond.assert_called_once()
    response_payload = json.loads(msg.respond.call_args[0][0].decode())
    assert response_payload == {"skipped": True}
    msg.ack.assert_called_once()
    msg.nak.assert_not_called()


async def test_health_returns_false_without_connection(worker):
    result = await worker.health()
    assert result is False


async def test_process_msg_processes_new_message(worker):
    msg = MagicMock()
    msg.headers = {
        "Arcana-Idempotency-Key": "key-new",
        "Arcana-Correlation-Id": "corr-2",
    }
    msg.data = json.dumps({"job_id": "job-99", "data": "world"}).encode()
    msg.respond = AsyncMock()
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()

    await worker.process_msg(msg)

    msg.ack.assert_called_once()
    msg.nak.assert_not_called()
    assert worker.is_processed("key-new") is True
    response_payload = json.loads(msg.respond.call_args[0][0].decode())
    assert "echo" in response_payload
