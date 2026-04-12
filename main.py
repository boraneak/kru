import asyncio
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from agent.session import gemini_session

app = FastAPI(title="Nova - Live Tutor")


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
    await websocket.accept()
    print("🔌 Student connected")
    await websocket.send_text(json.dumps({"type": "status", "data": "connected"}))

    audio_in_queue = asyncio.Queue()
    audio_out_queue = asyncio.Queue()
    video_out_queue = asyncio.Queue(maxsize=2)

    async def receive_from_browser():
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)

                if msg["type"] == "audio":
                    pcm = base64.b64decode(msg["data"])
                    await audio_out_queue.put(pcm)

                elif msg["type"] == "video":
                    if not video_out_queue.full():
                        await video_out_queue.put(msg["data"])

        except WebSocketDisconnect:
            print("🔌 Student disconnected")

    async def send_to_browser():
        try:
            while True:
                chunk = await audio_in_queue.get()
                if websocket.client_state.value == 3:
                    break
                await websocket.send_text(
                    json.dumps(
                        {"type": "audio", "data": base64.b64encode(chunk).decode()}
                    )
                )
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
