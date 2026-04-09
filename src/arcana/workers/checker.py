import json

from langchain_openai import ChatOpenAI

from arcana.workers.base import BaseWorker


CHECKER_PROMPT = """You are a fact-checker. Given a draft briefing and source chunks, verify each factual claim.

## Draft Briefing
{draft}

## Source Chunks
{chunks}

## Instructions
For each factual claim in the draft, determine if it's supported by the source chunks.
Return a JSON object with this exact structure:
{{"claims": [{{"text": "the claim", "verdict": "supported" | "unsupported" | "partial", "chunk_id": "relevant chunk id", "explanation": "brief explanation"}}]}}
Return ONLY valid JSON, no other text."""


class CheckerWorker(BaseWorker):
    def __init__(self, nats_url: str, subject: str, openai_api_key: str) -> None:
        super().__init__(nats_url, subject)
        self.llm = ChatOpenAI(model="gpt-4o", api_key=openai_api_key, temperature=0)

    async def handle(self, payload: dict) -> dict:
        job_id = payload["job_id"]
        draft = payload["draft"]
        chunks = payload["chunks"]
        chunk_ids = payload["chunk_ids"]
        chunks_text = "\n\n".join(
            f"[{cid}]\n{text}" for text, cid in zip(chunks, chunk_ids)
        )
        prompt = CHECKER_PROMPT.format(draft=draft, chunks=chunks_text)
        response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(raw)
        return {"job_id": job_id, "claims": result["claims"]}
