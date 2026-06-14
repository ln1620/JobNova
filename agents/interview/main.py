import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, silero

from agents import SelfIntroAgent, advance_after_recorded_answer
from userdata import InterviewUserData

root_env = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(root_env)
load_dotenv()

logger = logging.getLogger("jobnova-interview")


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    logger.info("Agent connected, waiting for candidate in room %s", ctx.room.name)

    participant = await ctx.wait_for_participant()
    email = ""
    user_id = 0
    interview_id = 0
    if participant.metadata:
        try:
            meta = json.loads(participant.metadata)
            email = meta.get("email", "")
            user_id = int(meta.get("user_id", 0))
            interview_id = int(meta.get("interview_id", 0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Bad participant metadata: %s", e)

    logger.info("Candidate joined: %s", email or participant.identity)

    llm_model = os.getenv("INTERVIEW_LLM", "google/gemini-2.5-flash-lite")
    tts_model = os.getenv("INTERVIEW_TTS_MODEL", "aura-2-andromeda-en")

    session = AgentSession[InterviewUserData](
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2-general"),
        llm=llm_model,
        tts=deepgram.TTS(model=tts_model),
        turn_detection="manual",
        userdata=InterviewUserData(
            email=email,
            user_id=user_id,
            interview_id=interview_id,
            room_name=ctx.room.name,
            api_base=os.getenv("API_URL", "http://localhost:8000"),
        ),
    )

    @ctx.room.on("data_received")
    def on_data_received(packet) -> None:
        try:
            payload = json.loads(packet.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if payload.get("type") != "answer_done":
            return
        logger.info("Candidate pressed Done — advancing stage")
        asyncio.create_task(advance_after_recorded_answer(session))

    await session.start(agent=SelfIntroAgent(), room=ctx.room)
    logger.info("Interview started — push-to-talk: record then Done")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="jobnova-interview",
        )
    )
