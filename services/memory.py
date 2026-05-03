from db.supabase import get_supabase

async def load_user_memory(user_id: str) -> list[dict]:
    """Load tutor memory for a user from Supabase."""
    client = get_supabase()
    result = client.table("tutor_memory") \
        .select("memory_text, category") \
        .eq("user_id", user_id) \
        .execute()
    return result.data or []

async def save_memory(user_id: str, memory_text: str, category: str):
    """Save a new memory after session ends."""
    client = get_supabase()
    client.table("tutor_memory").insert({
        "user_id": user_id,
        "memory_text": memory_text,
        "category": category,
    }).execute()