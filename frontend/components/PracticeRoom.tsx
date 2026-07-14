"use client";

import {
  BarVisualizer,
  RoomAudioRenderer,
  StartAudio,
  useLocalParticipant,
  useVoiceAssistant,
} from "@livekit/components-react";
import { useState } from "react";

import type { ConnectionDetails } from "@/lib/api";
import { languageMeta } from "@/lib/languages";
import { useTutorEvents } from "@/lib/useTutorEvents";
import { ErrorBanner } from "./ErrorBanner";
import { FlashcardExercise } from "./FlashcardExercise";
import { PushToTalk } from "./PushToTalk";
import { Transcript } from "./Transcript";

// The agent's own state. Note "listening" here means the tutor is *ready* for you
// — with push-to-talk the mic is muted until you hold, so we don't imply a hot mic.
const STATE_LABEL: Record<string, string> = {
  disconnected: "Disconnected",
  connecting: "Connecting…",
  initializing: "Warming up…",
  listening: "Ready",
  thinking: "Thinking…",
  speaking: "Speaking",
};

export function PracticeRoom({
  details,
  onLeave,
}: {
  details: ConnectionDetails;
  onLeave: () => void;
}) {
  const { state, audioTrack } = useVoiceAssistant();
  const { isMicrophoneEnabled } = useLocalParticipant();
  const tutor = useTutorEvents();
  const [dismissed, setDismissed] = useState<string | null>(null);
  const showError = tutor.error && tutor.error.message !== dismissed;

  return (
    <div>
      {showError && tutor.error && (
        <ErrorBanner error={tutor.error} onDismiss={() => setDismissed(tutor.error!.message)} />
      )}
      <div className="topbar">
        <div>
          <strong>Lingua</strong>
          <span className="lang-tag">
            {languageMeta(details.language).flag} {languageMeta(details.language).label}
          </span>
          <span className="who">· {details.identity}</span>
        </div>
        <button className="primary" onClick={onLeave}>
          End session
        </button>
      </div>

      <div className="practice">
        <FlashcardExercise state={tutor} />

        <div className="card practice-controls">
          <div className="pill-row">
            <div className="state-pill">
              <span className={`dot ${state}`} />
              {STATE_LABEL[state] ?? state}
            </div>
            <div className="state-pill">
              <span className={`dot ${isMicrophoneEnabled ? "speaking" : ""}`} />
              {isMicrophoneEnabled ? "Mic live" : "Mic off"}
            </div>
          </div>
          <div className="visualizer">
            <BarVisualizer
              state={state}
              barCount={7}
              trackRef={audioTrack}
              style={{ width: "100%", maxWidth: 280, height: 80 }}
            />
          </div>
          <PushToTalk />
        </div>

        <Transcript />
      </div>

      <RoomAudioRenderer />
      <StartAudio label="Click to enable audio" />
    </div>
  );
}
