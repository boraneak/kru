import asyncio
import base64
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, MODEL_NAME
from prompts.nova import NOVA_PROMPT

client = genai.Client(api_key=GEMINI_API_KEY)

CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": NOVA_PROMPT,
}


async def gemini_session(
    audio_in_queue: asyncio.Queue,
    audio_out_queue: asyncio.Queue,
    video_out_queue: asyncio.Queue,
):
    while True:
        try:
            print("🔄 Connecting to Gemini...")
            async with client.aio.live.connect(
                model=MODEL_NAME, config=CONFIG
            ) as session:
                print("✅ Nova is ready!")

                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                text="Start the session now. Greet the student and introduce yourself."
                            )
                        ],
                    )
                )

                async def send_audio():
                    while True:
                        data = await audio_out_queue.get()
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=data, mime_type="audio/pcm;rate=16000"
                            )
                        )

                async def send_video():
                    while True:
                        frame_b64 = await video_out_queue.get()
                        print("📷 Sending frame to Gemini")
                        await session.send_realtime_input(
                            video=types.Blob(
                                data=base64.b64decode(frame_b64), mime_type="image/jpeg"
                            )
                        )

                async def receive_audio():
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

                await asyncio.gather(
                    send_audio(),
                    send_video(),
                    receive_audio(),
                )

        except Exception as e:
            print(f"⚠️ Session error: {type(e).__name__}: {e}")
            print("🔄 Reconnecting in 3 seconds...")
            await asyncio.sleep(3)
