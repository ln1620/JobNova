import asyncio
import logging

from livekit.agents import Agent, AgentSession, RunContext, function_tool

from userdata import InterviewUserData, Stage

logger = logging.getLogger("jobnova-interview")

INTRO_QUESTION = "Can you please introduce yourself?"
EXPERIENCE_QUESTION = "Thank you. Explain about your past experiences."

INTRO_STAGE_TIMEOUT_SEC = 180
EXPERIENCE_STAGE_TIMEOUT_SEC = 180


async def advance_after_recorded_answer(session: AgentSession[InterviewUserData]) -> None:
    """Called when the candidate presses Done after recording their answer."""
    ud = session.userdata
    if ud.handoff_in_progress:
        return

    try:
        session.commit_user_turn()
    except Exception as e:
        logger.debug("commit_user_turn: %s", e)

    if ud.current_stage == Stage.SELF_INTRO:
        ud.self_intro_summary = "Candidate submitted a recorded self-introduction."
        ud.handoff_in_progress = True
        logger.info("Recorded answer → past experience")
        session.update_agent(PastExperienceAgent())
    elif ud.current_stage == Stage.PAST_EXPERIENCE:
        ud.experience_summary = "Candidate submitted a recorded past experience answer."
        ud.handoff_in_progress = True
        agent = session.current_agent
        if isinstance(agent, PastExperienceAgent):
            await agent._finish(ud)


class SelfIntroAgent(Agent):
    """Stage 1: one intro question, then wait for recorded answer."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You only speak the introduction question when the stage begins. "
                "Stay silent while the candidate records their answer. "
                "Do not ask follow-up questions."
            )
        )
        self._timer: asyncio.Task | None = None

    async def on_enter(self) -> None:
        ud: InterviewUserData = self.session.userdata
        ud.current_stage = Stage.SELF_INTRO
        ud.handoff_in_progress = False
        ud.waiting_for_recorded_answer = True
        self.session.say(INTRO_QUESTION, allow_interruptions=False)
        self._timer = asyncio.create_task(self._timeout_handoff(INTRO_STAGE_TIMEOUT_SEC))

    async def _timeout_handoff(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        ud: InterviewUserData = self.session.userdata
        if ud.current_stage == Stage.SELF_INTRO and not ud.handoff_in_progress:
            logger.info("Self-intro timeout → past experience")
            ud.self_intro_summary = ud.self_intro_summary or "Timed out waiting for introduction."
            ud.handoff_in_progress = True
            self.session.update_agent(PastExperienceAgent())

    @function_tool
    async def complete_self_intro(self, context: RunContext, summary: str):
        """Fallback tool if the model summarizes before handoff."""
        ud: InterviewUserData = context.userdata
        if ud.handoff_in_progress or ud.current_stage != Stage.SELF_INTRO:
            return
        ud.self_intro_summary = summary
        ud.handoff_in_progress = True
        if self._timer and not self._timer.done():
            self._timer.cancel()
        return PastExperienceAgent()


class PastExperienceAgent(Agent):
    """Stage 2: one experience question, then wait for recorded answer."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You only speak the past experience question when the stage begins. "
                "Stay silent while the candidate records their answer. "
                "Do not ask follow-up questions."
            )
        )
        self._timer: asyncio.Task | None = None

    async def on_enter(self) -> None:
        ud: InterviewUserData = self.session.userdata
        ud.current_stage = Stage.PAST_EXPERIENCE
        ud.handoff_in_progress = False
        ud.waiting_for_recorded_answer = True
        self.session.say(EXPERIENCE_QUESTION, allow_interruptions=False)
        self._timer = asyncio.create_task(self._timeout_finish(EXPERIENCE_STAGE_TIMEOUT_SEC))

    async def _timeout_finish(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        ud: InterviewUserData = self.session.userdata
        if ud.current_stage == Stage.PAST_EXPERIENCE and not ud.handoff_in_progress:
            logger.info("Past experience timeout → complete")
            ud.experience_summary = ud.experience_summary or "Timed out waiting for experience answer."
            await self._finish(ud)

    @function_tool
    async def complete_past_experience(self, context: RunContext, summary: str) -> None:
        ud: InterviewUserData = context.userdata
        if ud.current_stage == Stage.COMPLETE or ud.handoff_in_progress:
            return
        ud.experience_summary = summary
        ud.handoff_in_progress = True
        if self._timer and not self._timer.done():
            self._timer.cancel()
        await self._finish(ud)

    async def _finish(self, ud: InterviewUserData) -> None:
        if ud.current_stage == Stage.COMPLETE:
            return
        ud.current_stage = Stage.COMPLETE
        ud.handoff_in_progress = True
        ud.waiting_for_recorded_answer = False
        if self._timer and not self._timer.done():
            self._timer.cancel()

        import httpx

        payload = {
            "room_name": ud.room_name,
            "self_intro_summary": ud.self_intro_summary,
            "experience_summary": ud.experience_summary,
            "transcript": "\n".join(ud.transcript_parts),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{ud.api_base}/interview/complete", json=payload)
        except Exception as e:
            logger.warning("Failed to save interview: %s", e)

        self.session.say(
            "Thank you. Your mock interview is complete. "
            "Click End on the screen to view your summary.",
            allow_interruptions=False,
        )
