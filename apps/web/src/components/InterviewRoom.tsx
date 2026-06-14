"use client";

import { useCallback, useEffect, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
  useRoomContext,
  useVoiceAssistant,
} from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import { useRouter } from "next/navigation";

const STAGE_LABELS = [
  "Question 1: Self introduction",
  "Question 2: Past experience",
];

const QUESTIONS = [
  "Can you please introduce yourself?",
  "Thank you. Explain about your past experiences.",
];

function InterviewControls({ interviewId }: { interviewId: number }) {
  const state = useConnectionState();
  const router = useRouter();
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();
  const [stageIndex, setStageIndex] = useState(0);
  const [agentPresent, setAgentPresent] = useState(false);
  const [recording, setRecording] = useState(false);
  const [canRecord, setCanRecord] = useState(false);
  const [interviewDone, setInterviewDone] = useState(false);

  const { state: agentState } = useVoiceAssistant();

  useEffect(() => {
    const t1 = setTimeout(() => setStageIndex(1), 180_000);
    return () => clearTimeout(t1);
  }, []);

  useEffect(() => {
    const check = () => setAgentPresent(room.remoteParticipants.size > 0);
    check();
    room.on("participantConnected", check);
    room.on("participantDisconnected", check);
    return () => {
      room.off("participantConnected", check);
      room.off("participantDisconnected", check);
    };
  }, [room]);

  // Mic off until user presses Record
  useEffect(() => {
    if (!localParticipant) return;
    void localParticipant.setMicrophoneEnabled(false);
  }, [localParticipant]);

  // Enable Record after the agent finishes asking the current question
  useEffect(() => {
    if (!agentPresent || interviewDone) {
      setCanRecord(false);
      return;
    }
    if (agentState === "speaking") {
      setCanRecord(false);
      if (recording) {
        void localParticipant?.setMicrophoneEnabled(false);
        setRecording(false);
      }
    } else if (
      agentState === "listening" ||
      agentState === "idle" ||
      agentState === "thinking"
    ) {
      if (!recording) {
        setCanRecord(true);
      }
    }
  }, [agentState, agentPresent, interviewDone, recording, localParticipant]);

  const sendAnswerDone = useCallback(async () => {
    const data = new TextEncoder().encode(JSON.stringify({ type: "answer_done" }));
    await room.localParticipant.publishData(data, { reliable: true });
  }, [room]);

  async function toggleRecord() {
    if (!localParticipant || !canRecord || interviewDone) return;

    if (!recording) {
      await localParticipant.setMicrophoneEnabled(true);
      setRecording(true);
      setCanRecord(true);
    } else {
      await localParticipant.setMicrophoneEnabled(false);
      setRecording(false);
      setCanRecord(false);
      await sendAnswerDone();
      if (stageIndex === 0) {
        setStageIndex(1);
      } else {
        setInterviewDone(true);
      }
    }
  }

  let statusText = "Connecting…";
  if (state === ConnectionState.Connected) {
    if (!agentPresent) {
      statusText = "Waiting for interviewer…";
    } else if (agentState === "speaking") {
      statusText = "Listen to the question";
    } else if (recording) {
      statusText = "Recording your answer — press Done when finished";
    } else if (canRecord) {
      statusText = "Press Record and speak your answer";
    } else if (interviewDone) {
      statusText = "Interview complete";
    } else {
      statusText = "Get ready for the next question";
    }
  }

  return (
    <div className="flex flex-col items-center gap-6 py-10">
      <div className="rounded-full bg-violet-500/20 px-4 py-1.5 text-sm font-medium text-violet-200">
        {interviewDone ? "Complete" : STAGE_LABELS[stageIndex]}
      </div>

      <div className="flex h-36 w-36 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-blue-600">
        <span className="text-5xl">
          {recording ? "🔴" : agentPresent ? "🎙️" : "⏳"}
        </span>
      </div>

      <p className="max-w-md text-center text-lg text-slate-200">{statusText}</p>
      <p className="max-w-sm text-center text-sm text-slate-400">
        {QUESTIONS[Math.min(stageIndex, 1)]}
      </p>

      <button
        type="button"
        onClick={toggleRecord}
        disabled={!canRecord && !recording}
        className={`rounded-full px-10 py-4 text-lg font-semibold transition ${
          recording
            ? "bg-red-500 text-white hover:bg-red-400"
            : "bg-emerald-500 text-[#0b1020] hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
        }`}
      >
        {recording ? "Done" : "Record"}
      </button>

      <button
        type="button"
        onClick={() => router.push(`/interview/results/${interviewId}`)}
        className="rounded-full border border-white/20 px-6 py-2.5 text-sm text-white hover:bg-white/10"
      >
        End & view results
      </button>
    </div>
  );
}

export function InterviewRoom({
  token,
  serverUrl,
  interviewId,
}: {
  token: string;
  serverUrl: string;
  interviewId: number;
}) {
  return (
    <LiveKitRoom
      token={token}
      serverUrl={serverUrl}
      connect={true}
      audio={true}
      video={false}
      className="min-h-[60vh]"
    >
      <RoomAudioRenderer />
      <InterviewControls interviewId={interviewId} />
    </LiveKitRoom>
  );
}
