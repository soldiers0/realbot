import datetime

import databases
from databases import Database


class DBTools:
    db_to_python: dict[str, type] = {
        'character varying': str,
        'timestamp without time zone': datetime.datetime,
        'integer': int,
        'double precision': float,
        'text': str,
        'boolean': bool
    }

    python_to_db: dict[type, str] = {v: k for k, v in db_to_python.items()}

    @staticmethod
    async def runSql(sql: str) -> list[databases.core.Record]:
        database = Database('postgresql://postgres:Kys2281337@194.36.161.123:8001/real_base')
        await database.connect()
        rows = await database.fetch_all(
            query=sql)
        await database.disconnect()
        return rows
