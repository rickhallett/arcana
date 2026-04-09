import chromadb


class VectorStore:
    COLLECTION_NAME = "arcana_docs"

    def __init__(
        self,
        persist_dir: str | None = None,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
    ) -> None:
        if host:
            self._client = chromadb.HttpClient(host=host, port=port or 8000)
        elif persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.EphemeralClient()
        name = collection_name or self.COLLECTION_NAME
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"})

    def add_chunks(self, documents: list[str], ids: list[str], metadatas: list[dict]) -> None:
        if not documents:
            return
        self._collection.add(documents=documents, ids=ids, metadatas=metadatas)

    def query(self, query_text: str, n_results: int = 10, where: dict | None = None) -> dict:
        kwargs: dict = {"query_texts": [query_text], "n_results": n_results}
        if where:
            kwargs["where"] = where
        results = self._collection.query(**kwargs)
        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }

    def count(self) -> int:
        return self._collection.count()
