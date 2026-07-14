"use client";

import { useTranscriptions, useVoiceAssistant } from "@livekit/components-react";
import { useEffect, useRef } from "react";

export function Transcript() {
  const segments = useTranscriptions();
  const { agent } = useVoiceAssistant();
  const agentId = agent?.identity;
  const scrollRef = useRef<HTMLDivElement>(null);

  // Keep the newest line in view as the transcript grows (new lines *and*
  // streaming text within the current line).
  const lastText = segments[segments.length - 1]?.text ?? "";
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [segments.length, lastText]);

  return (
    <div className="card">
      <h3>Transcript</h3>
      <div className="transcript" ref={scrollRef}>
        {segments.length === 0 ? (
          <div className="muted">Your words will appear here as you speak…</div>
        ) : (
          segments.map((seg, i) => {
            const isAgent = seg.participantInfo.identity === agentId;
            return (
              <div key={i} className={`turn ${isAgent ? "agent" : "user"}`}>
                <div className="role">{isAgent ? "Lingua" : "You"}</div>
                <div>{seg.text}</div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
