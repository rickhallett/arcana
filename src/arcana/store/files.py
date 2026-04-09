import hashlib
from pathlib import Path


class FileStore:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)

    def save(self, job_id: str, content: bytes, filename: str) -> tuple[str, str]:
        checksum = hashlib.sha256(content).hexdigest()
        ext = Path(filename).suffix
        dir_path = self.base_dir / job_id
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{checksum}{ext}"
        file_path.write_bytes(content)
        return str(file_path), checksum

    def read(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def verify(self, path: str, expected_checksum: str) -> bool:
        content = self.read(path)
        actual = hashlib.sha256(content).hexdigest()
        return actual == expected_checksum
