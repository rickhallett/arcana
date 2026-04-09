import hashlib

from arcana.store.files import FileStore


def test_save_returns_path_and_checksum(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"hello arcana"
    path, checksum = store.save("job-001", content, "doc.pdf")

    expected_checksum = hashlib.sha256(content).hexdigest()
    assert checksum == expected_checksum
    assert path.endswith(f"{checksum}.pdf")


def test_save_creates_file_on_disk(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"some file content"
    path, _ = store.save("job-002", content, "report.txt")

    from pathlib import Path
    assert Path(path).exists()
    assert Path(path).read_bytes() == content


def test_read_returns_original_content(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"read me back"
    path, _ = store.save("job-003", content, "data.bin")

    result = store.read(path)
    assert result == content


def test_verify_with_valid_checksum_returns_true(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"verify this"
    path, checksum = store.save("job-004", content, "verify.pdf")

    assert store.verify(path, checksum) is True


def test_verify_with_invalid_checksum_returns_false(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"tampered content"
    path, _ = store.save("job-005", content, "bad.pdf")

    assert store.verify(path, "deadbeef" * 8) is False


def test_save_same_content_twice_is_idempotent(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"idempotent"
    path1, cs1 = store.save("job-006", content, "file.txt")
    path2, cs2 = store.save("job-006", content, "file.txt")

    assert path1 == path2
    assert cs1 == cs2


def test_save_different_jobs_use_separate_directories(tmp_path):
    store = FileStore(str(tmp_path))
    content = b"shared content"
    path_a, _ = store.save("job-a", content, "f.txt")
    path_b, _ = store.save("job-b", content, "f.txt")

    from pathlib import Path
    assert Path(path_a).parent.name == "job-a"
    assert Path(path_b).parent.name == "job-b"
