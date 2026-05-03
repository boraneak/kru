import asyncio
import json
import base64
import aiohttp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from agent.session import gemini_session
from config import SUPABASE_URL, SUPABASE_ANON_KEY

app = FastAPI(title="Nova - Live Tutor")

INBOUND_EVENT_TYPES = {"audio", "video", "ping"}


async def send_event(websocket: WebSocket, event_type: str, data: str):
    await websocket.send_text(json.dumps({"type": event_type, "data": data}))


def parse_inbound_event(raw: str):
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid_json"

    if not isinstance(msg, dict):
        return None, "invalid_event_shape"

    event_type = msg.get("type")
    data = msg.get("data")

    if event_type not in INBOUND_EVENT_TYPES:
        return None, "unsupported_event_type"

    if event_type in {"audio", "video"} and not isinstance(data, str):
        return None, "invalid_data_payload"

    return msg, None


async def verify_supabase_token(access_token: str) -> tuple[dict, str]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return {}, "4001: missing_supabase_config"
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "apikey": SUPABASE_ANON_KEY,
        }
        try:
            async with session.get(
                f"{SUPABASE_URL.rstrip('/')}/auth/v1/user", headers=headers, timeout=10
            ) as resp:
                if resp.status != 200:
                    return {}, f"4002: invalid_access_token (status {resp.status})"
                payload = await resp.json()
                return payload, ""
        except aiohttp.ClientError as e:
            return {}, f"4003: supabase_request_failed: {str(e)}"


@app.get("/")
async def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

    return {
        "message": "Nova API is running 🎓",
        "status": "healthy",
        "websocket": ws_url,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    access_token = websocket.query_params.get("token")

    if not access_token:
        await websocket.accept()
        await send_event(websocket, "error", "4000: missing_access_token")
        await websocket.close(code=4000)
        return

    user, auth_error = await verify_supabase_token(access_token)
    if auth_error:
        await websocket.accept()
        await send_event(websocket, "error", auth_error)
        await websocket.close(code=int(auth_error.split(":")[0]))
        return

    await websocket.accept()
    user_id = user.get("id", "unknown_user")
    print(f"🔌 Student connected: {user_id}")
    await send_event(websocket, "status", "connected")

    audio_in_queue = asyncio.Queue()
    audio_out_queue = asyncio.Queue()
    video_out_queue = asyncio.Queue(maxsize=2)

    async def receive_from_browser():
        try:
            while True:
                raw = await websocket.receive_text()
                msg, error = parse_inbound_event(raw)

                if error:
                    await send_event(websocket, "error", error)
                    continue

                if msg["type"] == "audio":
                    try:
                        pcm = base64.b64decode(msg["data"])
                    except Exception:
                        await send_event(websocket, "error", "invalid_audio_payload")
                        continue
                    await audio_out_queue.put(pcm)

                elif msg["type"] == "video":
                    if not video_out_queue.full():
                        await video_out_queue.put(msg["data"])
                elif msg["type"] == "ping":
                    await send_event(websocket, "status", "pong")

        except WebSocketDisconnect:
            print("🔌 Student disconnected")

    async def send_to_browser():
        try:
            while True:
                chunk = await audio_in_queue.get()
                if websocket.client_state.value == 3:
                    break
                await send_event(websocket, "audio", base64.b64encode(chunk).decode())
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    try:
        await asyncio.gather(
            receive_from_browser(),
            send_to_browser(),
            gemini_session(audio_in_queue, audio_out_queue, video_out_queue),
        )
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
