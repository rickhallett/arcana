import base64

import fitz  # pymupdf
from langchain_openai import ChatOpenAI

from arcana.workers.base import BaseWorker


class ExtractorWorker(BaseWorker):
    def __init__(self, nats_url: str, subject: str, uploads_dir: str, openai_api_key: str) -> None:
        super().__init__(nats_url, subject)
        self.uploads_dir = uploads_dir
        self.llm = ChatOpenAI(model="gpt-4o", api_key=openai_api_key, temperature=0)

    async def handle(self, payload: dict) -> dict:
        job_id = payload["job_id"]
        file_path = payload["file_path"]
        doc_type = payload["doc_type"]
        if doc_type == "pdf":
            text, title, pages = self._extract_pdf(file_path)
        elif doc_type in ("image", "url"):
            text, title = await self._extract_with_vlm(file_path, doc_type)
            pages = 1
        else:
            raise ValueError(f"Unsupported doc_type: {doc_type}")
        return {
            "job_id": job_id,
            "text": text,
            "title": title or "Untitled",
            "pages": pages,
            "doc_type": doc_type,
        }

    def _extract_pdf(self, file_path: str) -> tuple[str, str, int]:
        doc = fitz.open(file_path)
        pages_text = [page.get_text() for page in doc]
        text = "\n\n".join(pages_text)
        title = doc.metadata.get("title", "") or "Untitled"
        return text, title, len(doc)

    async def _extract_with_vlm(self, file_path: str, doc_type: str) -> tuple[str, str]:
        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        response = await self.llm.ainvoke([{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Extract all text content from this image. Preserve structure."
                        " Return the extracted text and suggest a title."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
            ],
        }])
        return response.content, "Untitled"
