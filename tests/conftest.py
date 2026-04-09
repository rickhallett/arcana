import pytest

from arcana.store.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await database.init()
    yield database
    await database.close()
