import asyncio
from datetime import datetime
from db.supabase import get_supabase


async def log_event(user_id: str, event_type: str, metadata: dict = {}):
    def _write():
        client = get_supabase()
        client.table("usage_logs").insert({
            "user_id": user_id,
            "event_type": event_type,
            "metadata": metadata,
        }).execute()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write)


async def start_session(user_id: str) -> int:
    client = get_supabase()
    result = client.table("sessions").insert({
        "user_id": user_id,
        "start_time": datetime.utcnow().isoformat(),
    }).execute()
    return result.data[0]["id"]


async def end_session(session_id: int, duration_seconds: int):
    client = get_supabase()
    client.table("sessions").update({
        "end_time": datetime.utcnow().isoformat(),
        "duration_seconds": duration_seconds,
    }).eq("id", session_id).execute()