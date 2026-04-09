import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from arcana.orchestrator.nats_dispatch import DispatchError, NATSDispatcher


def make_dispatcher(**kwargs) -> NATSDispatcher:
    defaults = {
        "nats_url": "nats://localhost:4222",
        "max_retries": 3,
        "retry_base_delay": 0.01,
        "retry_max_delay": 0.04,
        "ack_timeout": 5,
    }
    defaults.update(kwargs)
    return NATSDispatcher(**defaults)


def make_response(data: dict) -> SimpleNamespace:
    return SimpleNamespace(data=json.dumps(data).encode())


class TestMakeHeaders:
    def test_idempotency_key_format(self):
        d = make_dispatcher()
        headers = d._make_headers("job-123", "extract", 1, "corr-abc")
        assert headers["Arcana-Idempotency-Key"] == "job-123:extract:1"

    def test_correlation_id_passed_through(self):
        d = make_dispatcher()
        headers = d._make_headers("job-123", "extract", 2, "corr-xyz")
        assert headers["Arcana-Correlation-Id"] == "corr-xyz"

    def test_attempt_increments_in_key(self):
        d = make_dispatcher()
        h1 = d._make_headers("j", "s", 1, "c")
        h2 = d._make_headers("j", "s", 2, "c")
        assert h1["Arcana-Idempotency-Key"] != h2["Arcana-Idempotency-Key"]
        assert h2["Arcana-Idempotency-Key"] == "j:s:2"


class TestDispatchSuccess:
    async def test_dispatch_returns_parsed_response(self):
        d = make_dispatcher()
        expected = {"text": "hello", "pages": 5}
        mock_nc = MagicMock()
        mock_nc.request = AsyncMock(return_value=make_response(expected))
        d._nc = mock_nc

        result = await d.dispatch(
            subject="arcana.extract",
            payload={"job_id": "j1", "file_path": "/tmp/foo.pdf"},
            job_id="j1",
            step="extract",
            correlation_id="j1",
        )

        assert result == expected
        mock_nc.request.assert_awaited_once()

    async def test_dispatch_passes_correct_subject(self):
        d = make_dispatcher()
        mock_nc = MagicMock()
        mock_nc.request = AsyncMock(return_value=make_response({"ok": True}))
        d._nc = mock_nc

        await d.dispatch(
            subject="arcana.embed",
            payload={},
            job_id="j2",
            step="embed",
            correlation_id="j2",
        )

        call_args = mock_nc.request.call_args
        assert call_args[0][0] == "arcana.embed"


class TestDispatchRetry:
    async def test_dispatch_retries_on_failure_then_raises(self):
        d = make_dispatcher(max_retries=3, retry_base_delay=0.01, retry_max_delay=0.04)
        mock_nc = MagicMock()
        mock_nc.request = AsyncMock(side_effect=TimeoutError("timed out"))

        # DLQ publish will also fail — that's fine
        mock_js = MagicMock()
        mock_js.publish = AsyncMock(side_effect=Exception("no stream"))
        mock_nc.jetstream = MagicMock(return_value=mock_js)
        d._nc = mock_nc

        with pytest.raises(DispatchError) as exc_info:
            await d.dispatch(
                subject="arcana.extract",
                payload={},
                job_id="j3",
                step="extract",
                correlation_id="j3",
            )

        err = exc_info.value
        assert err.attempts == 3
        assert err.subject == "arcana.extract"
        assert err.job_id == "j3"
        # request was called exactly max_retries times
        assert mock_nc.request.call_count == 3

    async def test_dispatch_error_message_contains_subject_and_attempts(self):
        d = make_dispatcher(max_retries=2, retry_base_delay=0.01)
        mock_nc = MagicMock()
        mock_nc.request = AsyncMock(side_effect=Exception("boom"))
        mock_js = MagicMock()
        mock_js.publish = AsyncMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)
        d._nc = mock_nc

        with pytest.raises(DispatchError) as exc_info:
            await d.dispatch(
                subject="arcana.check",
                payload={},
                job_id="j4",
                step="check",
                correlation_id="j4",
            )

        assert "arcana.check" in str(exc_info.value)
        assert "2" in str(exc_info.value)
