"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  fetchProgress,
  type Language,
  type LearnerProgress,
  type WordProgress,
} from "@/lib/api";
import { LANGUAGES } from "@/lib/languages";
import { formatLastPracticed, scorePercent } from "@/lib/progress";

const HANDLE_KEY = "lingua.handle";

export default function HistoryPage() {
  const router = useRouter();
  const [handle, setHandle] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [language, setLanguage] = useState<Language | null>(null);
  const [progress, setProgress] = useState<LearnerProgress | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reuse the name entered on the landing page; ask for one only if missing.
  useEffect(() => {
    const saved = window.localStorage.getItem(HANDLE_KEY);
    if (saved) setHandle(saved);
  }, []);

  async function choose(lang: Language) {
    setLanguage(lang);
    setLoading(true);
    setError(null);
    setProgress(null);
    try {
      setProgress(await fetchProgress(handle, lang));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load your progress.");
    } finally {
      setLoading(false);
    }
  }

  function saveName() {
    const h = nameInput.trim();
    if (!h) return;
    window.localStorage.setItem(HANDLE_KEY, h);
    setHandle(h);
  }

  // --- name gate: only shown when no saved name exists ---------------------
  if (!handle) {
    return (
      <div className="hero">
        <div className="hero-card">
          <div className="flag">📚</div>
          <h1>Your history</h1>
          <p>Enter your name to see your saved progress.</p>
          <div className="field" style={{ marginTop: 8 }}>
            <input
              type="text"
              placeholder="Enter your name"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveName()}
              aria-label="Your name"
              style={{ flex: 1 }}
            />
            <button
              className="primary"
              onClick={saveName}
              disabled={!nameInput.trim()}
            >
              Continue
            </button>
          </div>
          <p className="muted" style={{ marginTop: 14, fontSize: 13 }}>
            <a onClick={() => router.push("/")} style={{ cursor: "pointer" }}>
              ← Back home
            </a>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <strong>Lingua</strong>
          <span className="who">· {handle}&apos;s history</span>
        </div>
        <button className="primary" onClick={() => router.push("/")}>
          Back home
        </button>
      </div>

      <div className="container">
        <div className="card">
          <h3>Lesson history</h3>
          <p className="muted" style={{ marginTop: -4 }}>
            Choose a language to see your progress.
          </p>
          <div
            className="lang-row"
            role="group"
            aria-label="Choose a language"
            style={{ marginTop: 12 }}
          >
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                className={`lang-pill ${language === l.code ? "selected" : ""}`}
                onClick={() => choose(l.code)}
                aria-pressed={language === l.code}
              >
                <span className="lang-flag">{l.flag}</span> {l.label}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="loading-block">
            <div className="spinner" />
            <span className="muted">Loading your progress…</span>
          </div>
        )}
        {error && !loading && <p className="error">{error}</p>}
        {progress && !loading && <ProgressReport progress={progress} />}
        {!progress && !loading && !error && (
          <p className="muted">Pick a language above to view your past lessons.</p>
        )}
      </div>
    </div>
  );
}

function ProgressReport({ progress }: { progress: LearnerProgress }) {
  const { profile, items, score } = progress;
  const last = formatLastPracticed(profile.last_seen);
  const pct = scorePercent(score.passed, score.total);

  return (
    <>
      <div className="card">
        <h3>Words studied</h3>
        <p className="muted" style={{ marginTop: -4 }}>
          Last practiced: {last ?? "—"}
        </p>
        <div style={{ marginTop: 8 }}>
          {items.map((it) => (
            <WordRow key={it.prompt} item={it} />
          ))}
        </div>
      </div>

      <div className="card" style={{ textAlign: "center" }}>
        <h3>Overall score</h3>
        <div className="score-big">
          {score.passed} / {score.total}{" "}
          <span className="muted">({pct}% correct)</span>
        </div>
        <p className="muted">Attempts don&apos;t count — a word passes once you get it right.</p>
      </div>
    </>
  );
}

function WordRow({ item }: { item: WordProgress }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "10px 0",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div>
        <div style={{ fontWeight: 600 }}>{item.prompt}</div>
        {item.word && (
          <div className="muted" style={{ fontSize: 13 }}>
            {item.word}
          </div>
        )}
      </div>
      {/* Reuse the flashcard result pill styling (green/red). */}
      <span className="flashcard-result" style={{ margin: 0, minHeight: 0 }}>
        <span className={`thumb ${item.passed ? "up" : "down"}`}>
          {item.passed ? "👍" : "👎"}
        </span>
      </span>
    </div>
  );
}
