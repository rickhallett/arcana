import asyncio
import json

import nats

from arcana.log import log


class DispatchError(Exception):
    def __init__(self, subject: str, job_id: str, attempts: int, last_error: str):
        self.subject = subject
        self.job_id = job_id
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"Dispatch to {subject} failed after {attempts} attempts: {last_error}")


class NATSDispatcher:
    def __init__(
        self,
        nats_url: str,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        retry_max_delay: float = 16.0,
        ack_timeout: int = 30,
    ) -> None:
        self.nats_url = nats_url
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.ack_timeout = ack_timeout
        self._nc = None

    async def connect(self) -> None:
        self._nc = await nats.connect(self.nats_url)

    async def close(self) -> None:
        if self._nc:
            await self._nc.close()
            self._nc = None

    def _make_headers(self, job_id: str, step: str, attempt: int, correlation_id: str) -> dict:
        return {
            "Arcana-Idempotency-Key": f"{job_id}:{step}:{attempt}",
            "Arcana-Correlation-Id": correlation_id,
        }

    async def dispatch(
        self,
        subject: str,
        payload: dict,
        job_id: str,
        step: str,
        correlation_id: str,
    ) -> dict:
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                headers = self._make_headers(job_id, step, attempt, correlation_id)
                response = await self._nc.request(
                    subject,
                    json.dumps(payload).encode(),
                    timeout=self.ack_timeout,
                    headers=headers,
                )
                result = json.loads(response.data.decode())
                log(
                    "dispatch",
                    "info",
                    "dispatch_ok",
                    {"subject": subject, "job_id": job_id, "step": step, "attempt": attempt},
                    correlation_id,
                )
                return result
            except Exception as e:
                last_error = str(e)
                log(
                    "dispatch",
                    "warning",
                    "dispatch_retry",
                    {
                        "subject": subject,
                        "job_id": job_id,
                        "step": step,
                        "attempt": attempt,
                        "error": last_error,
                    },
                    correlation_id,
                )
                if attempt < self.max_retries:
                    delay = min(
                        self.retry_base_delay * (2 ** (attempt - 1)),
                        self.retry_max_delay,
                    )
                    await asyncio.sleep(delay)

        await self._publish_dlq(subject, payload, job_id, step, last_error, correlation_id)
        raise DispatchError(subject, job_id, self.max_retries, last_error)

    async def _publish_dlq(
        self,
        subject: str,
        payload: dict,
        job_id: str,
        step: str,
        error: str,
        correlation_id: str,
    ) -> None:
        dlq_subject = f"arcana.dlq.{step}"
        dlq_payload = {
            "original_subject": subject,
            "original_payload": payload,
            "job_id": job_id,
            "step": step,
            "error": error,
            "attempts": self.max_retries,
        }
        try:
            js = self._nc.jetstream()
            await js.publish(dlq_subject, json.dumps(dlq_payload).encode())
            log(
                "dispatch",
                "error",
                "dlq_published",
                {"subject": dlq_subject, "job_id": job_id},
                correlation_id,
            )
        except Exception as e:
            log(
                "dispatch",
                "error",
                "dlq_publish_failed",
                {"error": str(e), "job_id": job_id},
                correlation_id,
            )
