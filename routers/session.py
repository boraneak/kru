import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import jwt

from db.supabase import get_supabase, verify_token
from services.memory import load_user_memory, save_memory
from services.tracker import log_event, start_session, end_session
from services.gemini import run_gemini_session
from prompts.nova import build_prompt

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # --- STEP 1: Auth ---
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        user_id = verify_token(token)
    except jwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return
    except jwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    print(f"✅ User authenticated: {user_id}")

    # --- STEP 2: Load memory + build prompt ---
    memories = await load_user_memory(user_id)
    system_prompt = build_prompt(memories)

    # --- STEP 3: Start tracking ---
    session_id = await start_session(user_id)
    session_start = datetime.utcnow()
    await log_event(user_id, "session_start", {"session_id": session_id})

    # --- STEP 4: Run session ---
    audio_in_queue = asyncio.Queue()
    audio_out_queue = asyncio.Queue()
    video_out_queue = asyncio.Queue(maxsize=2)

    import json
    import base64

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
            pass

    async def send_to_browser():
        try:
            while True:
                chunk = await audio_in_queue.get()
                if websocket.client_state.value == 3:
                    break
                await websocket.send_text(
                    json.dumps({
                        "type": "audio",
                        "data": base64.b64encode(chunk).decode()
                    })
                )
        except WebSocketDisconnect:
            pass

    try:
        await asyncio.gather(
            receive_from_browser(),
            send_to_browser(),
            run_gemini_session(
                system_prompt,
                audio_in_queue,
                audio_out_queue,
                video_out_queue,
            ),
        )
    except WebSocketDisconnect:
        pass
    finally:
        # --- STEP 5: Cleanup after disconnect ---
        duration = int((datetime.utcnow() - session_start).total_seconds())
        await end_session(session_id, duration)
        await log_event(user_id, "session_end", {
            "session_id": session_id,
            "duration_seconds": duration,
        })
        print(f"👋 Session ended for user {user_id} — {duration}s")
