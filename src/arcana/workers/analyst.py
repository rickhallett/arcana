import re

from langchain_anthropic import ChatAnthropic

from arcana.workers.base import BaseWorker


ANALYST_PROMPT = """You are a research analyst. Answer the question based ONLY on the provided source chunks. Cite your sources using [N] notation where N is the chunk number (1-indexed).

## Source Chunks
{chunks}

## Question
{question}

## Instructions
- Answer thoroughly but concisely
- Cite every factual claim with [N] referencing the chunk number
- If the sources don't contain enough information, say so explicitly
- Do not invent information not present in the sources"""


class AnalystWorker(BaseWorker):
    def __init__(self, nats_url: str, subject: str, anthropic_api_key: str) -> None:
        super().__init__(nats_url, subject)
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=anthropic_api_key,
            temperature=0,
            max_tokens=4096,
        )

    async def handle(self, payload: dict) -> dict:
        job_id = payload["job_id"]
        question = payload["question"]
        chunks = payload["chunks"]
        chunk_ids = payload["chunk_ids"]
        chunks_text = "\n\n".join(
            f"[{i+1}] (id: {cid})\n{text}"
            for i, (text, cid) in enumerate(zip(chunks, chunk_ids))
        )
        prompt = ANALYST_PROMPT.format(chunks=chunks_text, question=question)
        response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
        draft = response.content
        citations = self._extract_citations(draft, chunk_ids)
        return {"job_id": job_id, "draft": draft, "citations": citations}

    def _extract_citations(self, text: str, chunk_ids: list[str]) -> list[dict]:
        refs = set(re.findall(r"\[(\d+)\]", text))
        return [
            {"ref": int(ref), "chunk_id": chunk_ids[int(ref) - 1]}
            for ref in sorted(refs)
            if 0 <= int(ref) - 1 < len(chunk_ids)
        ]
