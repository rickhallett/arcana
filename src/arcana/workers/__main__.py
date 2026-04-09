import asyncio
import sys

from arcana.config import Settings


async def main() -> None:
    settings = Settings()
    worker_type = settings.worker_type
    if worker_type == "extractor":
        from arcana.workers.extractor import ExtractorWorker
        worker = ExtractorWorker(
            nats_url=settings.nats_url,
            subject="arcana.extract",
            uploads_dir=settings.uploads_dir,
            openai_api_key=settings.openai_api_key,
        )
    elif worker_type == "embedder":
        from arcana.workers.embedder import EmbedderWorker
        worker = EmbedderWorker(
            nats_url=settings.nats_url,
            subject="arcana.embed",
            openai_api_key=settings.openai_api_key,
            chroma_host=settings.chroma_host,
            chroma_port=settings.chroma_port,
        )
    elif worker_type == "analyst":
        from arcana.workers.analyst import AnalystWorker
        worker = AnalystWorker(
            nats_url=settings.nats_url,
            subject="arcana.analyse",
            anthropic_api_key=settings.anthropic_api_key,
        )
    elif worker_type == "checker":
        from arcana.workers.checker import CheckerWorker
        worker = CheckerWorker(
            nats_url=settings.nats_url,
            subject="arcana.check",
            openai_api_key=settings.openai_api_key,
        )
    else:
        print(f"Unknown worker type: {worker_type}", file=sys.stderr)
        sys.exit(1)
    # Stagger startup by worker type to avoid thundering herd on NATS
    stagger = {"extractor": 0, "embedder": 3, "analyst": 6, "checker": 9}
    delay = stagger.get(worker_type, 0)
    if delay:
        await asyncio.sleep(delay)
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
