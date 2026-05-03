# services/gemini.py
import asyncio
import base64
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, MODEL_NAME

client = genai.Client(api_key=GEMINI_API_KEY)


def build_config(system_prompt: str) -> dict:
    """Build Gemini session config with user-specific prompt."""
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_prompt,
    }


async def send_audio(session, audio_out_queue: asyncio.Queue):
    while True:
        data = await audio_out_queue.get()
        await session.send_realtime_input(
            audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
        )


async def send_video(session, video_out_queue: asyncio.Queue):
    while True:
        frame_b64 = await video_out_queue.get()
        await session.send_realtime_input(
            video=types.Blob(
                data=base64.b64decode(frame_b64),
                mime_type="image/jpeg"
            )
        )


async def receive_audio(session, audio_in_queue: asyncio.Queue):
    while True:
        async for message in session.receive():
            if (
                message.server_content
                and message.server_content.model_turn
            ):
                for part in message.server_content.model_turn.parts:
                    if (
                        hasattr(part, "inline_data")
                        and part.inline_data
                        and part.inline_data.data
                    ):
                        await audio_in_queue.put(part.inline_data.data)


async def run_gemini_session(
    system_prompt: str,
    audio_in_queue: asyncio.Queue,
    audio_out_queue: asyncio.Queue,
    video_out_queue: asyncio.Queue,
):
    """Main Gemini session loop with reconnect logic."""
    while True:
        try:
            print("🔄 Connecting to Gemini...")
            async with client.aio.live.connect(
                model=MODEL_NAME,
                config=build_config(system_prompt),
            ) as session:
                print("✅ Nova is ready!")

                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(
                            text="Start the session now. Greet the student and introduce yourself."
                        )],
                    )
                )

                await asyncio.gather(
                    send_audio(session, audio_out_queue),
                    send_video(session, video_out_queue),
                    receive_audio(session, audio_in_queue),
                )

        except Exception as e:
            print(f"⚠️ Gemini error: {type(e).__name__}: {e}")
            print("🔄 Reconnecting in 3 seconds...")
            await asyncio.sleep(3)
            