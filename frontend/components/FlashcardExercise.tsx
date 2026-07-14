"use client";

import { useState } from "react";
import type { TutorState } from "@/lib/tutorEvents";
import { Spinner } from "./Spinner";

export function FlashcardExercise({ state }: { state: TutorState }) {
  const { item, done, tip } = state;

  if (done) {
    const pct = done.total > 0 ? Math.round((done.correct / done.total) * 100) : 0;
    return (
      <div className="card flashcard done">
        <div className="flashcard-emoji">🎉</div>
        <h2>Exercise complete!</h2>
        <div className="score-big">
          {done.correct} / {done.total} <span className="muted">({pct}%)</span>
        </div>
        <p className="muted">Great work — say “again” to practice once more.</p>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="card flashcard">
        <Spinner label="Getting your pronunciation practice ready…" />
      </div>
    );
  }

  return (
    <div className="card flashcard">
      <div className="flashcard-progress muted">
        Word {item.index} of {item.total}
      </div>

      <FlashcardImage image={item.image} emoji={item.emoji} alt={item.prompt_en} />

      <div className="flashcard-word">{item.prompt_target}</div>
      <div className="flashcard-en muted">{item.prompt_en}</div>

      <div className={`flashcard-result ${item.result ?? ""}`}>
        {item.result === "up" && <span className="thumb up">👍 Nice!</span>}
        {item.result === "down" && <span className="thumb down">👎 Try again</span>}
        {!item.result && <span className="muted">Hold the button and say it out loud</span>}
      </div>
      {tip && item.result === "down" && <div className="flashcard-tip">{tip}</div>}
    </div>
  );
}

function FlashcardImage({ image, emoji, alt }: { image: string; emoji: string; alt: string }) {
  const [broken, setBroken] = useState(false);
  if (!image || broken) {
    return <div className="flashcard-emoji" aria-label={alt}>{emoji || "🖼️"}</div>;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="flashcard-img"
      src={image}
      alt={alt}
      onError={() => setBroken(true)}
    />
  );
}
