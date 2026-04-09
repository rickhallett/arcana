from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def worker():
    with patch("arcana.workers.extractor.ChatOpenAI"):
        from arcana.workers.extractor import ExtractorWorker
        return ExtractorWorker(
            nats_url="nats://localhost:4222",
            subject="arcana.extract",
            uploads_dir="/tmp/uploads",
            openai_api_key="test-key",
        )


async def test_handle_pdf(worker, tmp_path):
    # Create a minimal real PDF using fitz so we avoid complex mocking of the doc iterator
    import fitz
    pdf_path = str(tmp_path / "test.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Hello PDF world")
    doc.set_metadata({"title": "Test Doc"})
    doc.save(pdf_path)
    doc.close()

    payload = {"job_id": "job-1", "file_path": pdf_path, "doc_type": "pdf"}
    result = await worker.handle(payload)

    assert result["job_id"] == "job-1"
    assert result["doc_type"] == "pdf"
    assert result["pages"] == 1
    assert result["title"] == "Test Doc"
    assert "Hello PDF world" in result["text"]


async def test_handle_image(worker, tmp_path):
    # Create a minimal PNG file (1x1 white pixel)
    img_path = str(tmp_path / "test.png")
    # Minimal valid PNG bytes (1x1 white pixel)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with open(img_path, "wb") as f:
        f.write(png_bytes)

    mock_response = MagicMock()
    mock_response.content = "Extracted text from image"
    worker.llm.ainvoke = AsyncMock(return_value=mock_response)

    payload = {"job_id": "job-2", "file_path": img_path, "doc_type": "image"}
    result = await worker.handle(payload)

    assert result["job_id"] == "job-2"
    assert result["doc_type"] == "image"
    assert result["pages"] == 1
    assert result["text"] == "Extracted text from image"
    assert result["title"] == "Untitled"
    worker.llm.ainvoke.assert_called_once()


async def test_handle_unsupported_doc_type(worker):
    payload = {"job_id": "job-3", "file_path": "/tmp/x.xyz", "doc_type": "video"}
    with pytest.raises(ValueError, match="Unsupported doc_type"):
        await worker.handle(payload)
