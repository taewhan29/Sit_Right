# Sit Right 서버 (뼈대)

현재는 이벤트를 검증해서 응답만 하고, 저장은 하지 않는다.

## 설치

```powershell
cd server
python -m venv server_env
server_env\Scripts\activate
pip install -r requirements.txt
```

## 실행

```powershell
cd server
server_env\scripts\activate
uvicorn main:app --reload
deactivate
```

## 확인

브라우저에서 http://127.0.0.1:8000/docs 를 연다.
- `GET /health` → `{"ok": true}`
- `POST /events` → "Try it out"에서 요청을 보낸다. 정상이면 200, 필수 필드가 빠지면 422.
