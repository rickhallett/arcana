from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from arcana.config import Settings
from arcana.orchestrator.nats_dispatch import NATSDispatcher
from arcana.store.database import Database
from arcana.store.documents import DocumentStore
from arcana.store.files import FileStore
from arcana.store.vectors import VectorStore


def create_app() -> FastAPI:
    settings = Settings()
    db = Database(settings.db_url)
    doc_store = DocumentStore(db)
    file_store = FileStore(settings.uploads_dir)
    if settings.chroma_host:
        vector_store = VectorStore(host=settings.chroma_host, port=settings.chroma_port)
    else:
        vector_store = VectorStore(persist_dir="store/chroma")
    dispatcher = NATSDispatcher(
        nats_url=settings.nats_url,
        max_retries=settings.max_retries,
        retry_base_delay=settings.retry_base_delay,
        retry_max_delay=settings.retry_max_delay,
        ack_timeout=settings.nats_ack_timeout,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.init()
        await doc_store.init_schema()
        with suppress(Exception):  # NATS may not be available in local dev
            await dispatcher.connect()
        yield
        await dispatcher.close()
        await db.close()

    app = FastAPI(title="Arcana", lifespan=lifespan)
    app.state.doc_store = doc_store
    app.state.file_store = file_store
    app.state.vector_store = vector_store
    app.state.dispatcher = dispatcher
    app.state.settings = settings
    templates_dir = Path(__file__).parent / "templates"
    if templates_dir.exists():
        app.state.templates = Jinja2Templates(directory=str(templates_dir))
    from arcana.gateway.routes import router
    app.include_router(router)
    return app
