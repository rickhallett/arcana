from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from arcana.store.vectors import VectorStore
from arcana.workers.base import BaseWorker


class EmbedderWorker(BaseWorker):
    def __init__(
        self,
        nats_url: str,
        subject: str,
        openai_api_key: str,
        chroma_persist_dir: str | None = None,
        chroma_host: str | None = None,
        chroma_port: int | None = None,
    ) -> None:
        super().__init__(nats_url, subject)
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", api_key=openai_api_key
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=50, length_function=len
        )
        self.vector_store = VectorStore(
            persist_dir=chroma_persist_dir, host=chroma_host, port=chroma_port
        )

    async def handle(self, payload: dict) -> dict:
        job_id = payload["job_id"]
        text = payload["text"]
        title = payload["title"]
        doc_type = payload["doc_type"]
        if not text.strip():
            return {
                "job_id": job_id,
                "chunk_count": 0,
                "collection": VectorStore.COLLECTION_NAME,
            }
        chunks = self.splitter.split_text(text)
        ids = [f"{job_id}-chunk-{i}" for i in range(len(chunks))]
        metadatas = [
            {"job_id": job_id, "title": title, "doc_type": doc_type, "chunk_index": i}
            for i in range(len(chunks))
        ]
        self.vector_store.add_chunks(chunks, ids, metadatas)
        return {
            "job_id": job_id,
            "chunk_count": len(chunks),
            "collection": VectorStore.COLLECTION_NAME,
        }
