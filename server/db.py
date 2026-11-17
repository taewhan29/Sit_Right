import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from schemas import EventIn

# 환경변수로 경로를 바꿀 수 있다. 없으면 server/data/events.db 를 쓴다.
DB_PATH = os.environ.get("SIT_RIGHT_DB_PATH") or str(Path(__file__).parent / "data" / "events.db")

# 임시 스키마: schemas.EventIn 과 함께 바뀔 수 있다.
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       TEXT NOT NULL UNIQUE,
    anon_id        TEXT NOT NULL,
    session_id     TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    warning_level  INTEGER,
    intervention   TEXT,
    deviation      REAL,
    app_version    TEXT NOT NULL,
    client_ts      TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    extra          TEXT,
    received_at    TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    # 요청마다 연결을 새로 연다: FastAPI 가 동기 엔드포인트를 스레드풀에서 실행하기 때문
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    # data/ 는 .gitignore 대상이라 새로 clone 하면 없다. 폴더가 없어도 서버가 뜨게 만든다
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect()) as conn, conn:
        conn.execute(_CREATE_SQL)


def save_event(event: EventIn) -> bool:
    """저장하면 True, event_id 중복이라 건너뛰면 False."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO events (
                event_id, anon_id, session_id, event_type, warning_level,
                intervention, deviation, app_version, client_ts,
                schema_version, extra, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.anon_id,
                event.session_id,
                event.event_type,
                event.warning_level,
                event.intervention,
                event.deviation,
                event.app_version,
                event.client_ts.isoformat(),
                event.schema_version,
                json.dumps(event.extra) if event.extra is not None else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.rowcount == 1
