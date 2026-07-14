"use client";

import { useLocalParticipant } from "@livekit/components-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Push-to-talk mic control. The microphone stays MUTED by default; it is only
 * live while the button is held (or the Space key is held), and mutes again on
 * release — so the tutor only hears you when you mean to speak.
 */
export function PushToTalk() {
  const { localParticipant } = useLocalParticipant();
  const [talking, setTalking] = useState(false);

  // Pre-acquire the mic + permission ONCE so the first hold is instant, then
  // immediately mute. The tutor receives NO audio until the learner holds the
  // button — the mic is not left open during practice.
  useEffect(() => {
    if (!localParticipant) return;
    let cancelled = false;
    (async () => {
      try {
        await localParticipant.setMicrophoneEnabled(true);
        if (!cancelled) await localParticipant.setMicrophoneEnabled(false);
      } catch {
        // permission will be requested on the first hold instead
      }
    })();
    return () => {
      cancelled = true;
      // Ensure we never leave the mic open when unmounting.
      localParticipant?.setMicrophoneEnabled(false);
    };
  }, [localParticipant]);

  const start = useCallback(() => {
    setTalking(true);
    localParticipant?.setMicrophoneEnabled(true);
  }, [localParticipant]);

  const stop = useCallback(() => {
    setTalking(false);
    localParticipant?.setMicrophoneEnabled(false);
  }, [localParticipant]);

  // Hold Space to talk (ignore auto-repeat and when typing in a field).
  useEffect(() => {
    const isTyping = (t: EventTarget | null) =>
      t instanceof HTMLElement && ["INPUT", "TEXTAREA"].includes(t.tagName);
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat && !isTyping(e.target)) {
        e.preventDefault();
        start();
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isTyping(e.target)) {
        e.preventDefault();
        stop();
      }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [start, stop]);

  const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    // Capture so we still get pointerup even if the finger/cursor drifts off.
    e.currentTarget.setPointerCapture?.(e.pointerId);
    start();
  };

  return (
    <div className="ptt-wrap">
      <button
        type="button"
        className={`ptt ${talking ? "talking" : ""}`}
        onPointerDown={onPointerDown}
        onPointerUp={stop}
        onPointerCancel={stop}
        onLostPointerCapture={stop}
        aria-pressed={talking}
      >
        <span className="ptt-dot" />
        {talking ? "Listening… release to send" : "Hold to speak"}
      </button>
      <div className="ptt-hint">Hold the button (or the Space bar) while you speak</div>
    </div>
  );
}
