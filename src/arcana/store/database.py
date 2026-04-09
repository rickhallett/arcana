import aiosqlite


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        path = self.url.split("///", 1)[1] if "///" in self.url else self.url
        self._conn = await aiosqlite.connect(path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialised — call init() first")
        return self._conn

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
