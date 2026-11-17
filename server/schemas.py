from datetime import datetime

from pydantic import BaseModel


# 임시 스키마: 연구 가설과 로그 필드가 확정되기 전이라 필드는 바뀔 수 있다.
class EventIn(BaseModel):
    event_id: str  # 클라이언트가 만든 고유 ID (재시도 중복 방지용)
    anon_id: str
    session_id: str
    event_type: str
    warning_level: int | None = None
    intervention: str | None = None
    deviation: float | None = None
    app_version: str
    client_ts: datetime  # 클라이언트가 이벤트 발생 시점에 UTC로 찍은 시각
    schema_version: int = 1
    extra: dict | None = None
