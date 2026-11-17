from contextlib import asynccontextmanager

from fastapi import FastAPI

import db
from schemas import EventIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Sit Right Server", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/events")
def post_event(event: EventIn):
    if db.save_event(event):
        return {"stored": True, "event_id": event.event_id}
    # 재시도로 같은 event_id 가 다시 온 경우: 오류가 아니라 정상 응답으로 알린다
    return {"stored": False, "duplicate": True, "event_id": event.event_id}
