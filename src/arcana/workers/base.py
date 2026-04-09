import json
from abc import ABC, abstractmethod

import nats
from nats.aio.client import Client as NATSClient

from arcana.log import log


class BaseWorker(ABC):
    def __init__(self, nats_url: str, subject: str) -> None:
        self.nats_url = nats_url
        self.subject = subject
        self._nc: NATSClient | None = None
        self._sub = None
        self._processed: set[str] = set()
        self._running = False

    @abstractmethod
    async def handle(self, payload: dict) -> dict:
        """Process a work request and return the result."""

    def make_idempotency_key(self, job_id: str, step: str, attempt: int) -> str:
        return f"{job_id}:{step}:{attempt}"

    def is_processed(self, key: str) -> bool:
        return key in self._processed

    def mark_processed(self, key: str) -> None:
        self._processed.add(key)

    async def process_msg(self, msg) -> None:
        headers = msg.headers or {}
        idem_key = headers.get("Arcana-Idempotency-Key", "")
        correlation_id = headers.get("Arcana-Correlation-Id", "")

        if idem_key and self.is_processed(idem_key):
            log(self.subject, "info", "duplicate_skipped", {"key": idem_key}, correlation_id)
            await msg.respond(json.dumps({"skipped": True}).encode())
            await msg.ack()
            return

        try:
            payload = json.loads(msg.data.decode())
            job_id = payload.get("job_id")
            log(self.subject, "info", "processing", {"job_id": job_id}, correlation_id)
            result = await self.handle(payload)
            if idem_key:
                self.mark_processed(idem_key)
            await msg.respond(json.dumps(result).encode())
            await msg.ack()
            log(self.subject, "info", "completed", {"job_id": job_id}, correlation_id)
        except Exception as e:
            log(self.subject, "error", "failed", {"error": str(e), "key": idem_key}, correlation_id)
            await msg.nak()

    async def start(self) -> None:
        self._nc = await nats.connect(self.nats_url)
        js = self._nc.jetstream()
        self._sub = await js.subscribe(
            self.subject, queue=f"{self.subject}-workers", manual_ack=True
        )
        self._running = True
        log(self.subject, "info", "worker_started", {"subject": self.subject})
        async for msg in self._sub.messages:
            if not self._running:
                break
            await self.process_msg(msg)

    async def stop(self) -> None:
        self._running = False
        if self._sub:
            await self._sub.unsubscribe()
        if self._nc:
            await self._nc.close()
        log(self.subject, "info", "worker_stopped")

    async def health(self) -> bool:
        return self._nc is not None and self._nc.is_connected
