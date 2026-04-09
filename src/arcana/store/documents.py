import uuid
from datetime import UTC, datetime

from arcana.store.database import Database

_INSERT_JOB = (
    "INSERT INTO jobs "
    "(id, job_type, status, file_path, file_checksum, filename, "
    "doc_type, question, created_at, updated_at) "
    "VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)"
)
_INSERT_REPORT = (
    "INSERT INTO reports "
    "(id, job_id, answer, claims_json, confidence, cost_usd, duration_s, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)


class DocumentStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def init_schema(self) -> None:
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', current_step TEXT,
                file_path TEXT, file_checksum TEXT, filename TEXT, doc_type TEXT,
                question TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE,
                answer TEXT NOT NULL, claims_json TEXT NOT NULL,
                confidence REAL NOT NULL, cost_usd REAL NOT NULL,
                duration_s REAL NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )""")

    async def create_job(self, job_type: str, file_path: str = "", file_checksum: str = "",
                         filename: str = "", doc_type: str = "", question: str = "") -> dict:
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            _INSERT_JOB,
            (job_id, job_type, file_path, file_checksum, filename, doc_type, question, now, now))
        return await self.get_job(job_id)

    async def create_query_job(self, question: str) -> dict:
        return await self.create_job(job_type="query", question=question)

    async def get_job(self, job_id: str) -> dict | None:
        return await self.db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))

    async def update_job_status(self, job_id: str, status: str, step: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            "UPDATE jobs SET status = ?, current_step = ?, updated_at = ? WHERE id = ?",
            (status, step, now, job_id))

    async def list_jobs(self, limit: int = 50) -> list[dict]:
        return await self.db.fetchall(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))

    async def list_incomplete_jobs(self) -> list[dict]:
        return await self.db.fetchall(
            "SELECT * FROM jobs WHERE status NOT IN ('completed', 'failed', 'pending')")

    async def save_report(self, job_id: str, answer: str, claims_json: str,
                          confidence: float, cost_usd: float, duration_s: float) -> None:
        report_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            _INSERT_REPORT,
            (report_id, job_id, answer, claims_json, confidence, cost_usd, duration_s, now))

    async def get_report(self, job_id: str) -> dict | None:
        return await self.db.fetchone("SELECT * FROM reports WHERE job_id = ?", (job_id,))
