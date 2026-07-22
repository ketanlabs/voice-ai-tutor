"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import type { Language } from "@/lib/api";
import { LANGUAGES } from "@/lib/languages";

const HANDLE_KEY = "lingua.handle";
const LANG_KEY = "lingua.language";

export default function Landing() {
  const router = useRouter();
  const [handle, setHandle] = useState("");
  const [language, setLanguage] = useState<Language>("es");

  useEffect(() => {
    const savedHandle = window.localStorage.getItem(HANDLE_KEY);
    if (savedHandle) setHandle(savedHandle);
    const savedLang = window.localStorage.getItem(LANG_KEY) as Language | null;
    if (savedLang) setLanguage(savedLang);
  }, []);

  function start() {
    const h = handle.trim();
    if (!h) return;
    window.localStorage.setItem(HANDLE_KEY, h);
    window.localStorage.setItem(LANG_KEY, language);
    router.push("/practice");
  }

  function viewHistory() {
    // Carry over a name typed but not yet "started" so history can reuse it.
    const h = handle.trim();
    if (h) window.localStorage.setItem(HANDLE_KEY, h);
    window.localStorage.setItem(LANG_KEY, language);
    router.push("/history");
  }

  const ready = handle.trim().length > 0;

  return (
    <div className="hero">
      <div className="hero-card">
        <div className="flag">🗣️</div>
        <h1>Lingua</h1>
        <p>
          Say it out loud. See a picture, hear the word, and practice your
          pronunciation in Spanish, French, or Italian.
        </p>

        <input
          type="text"
          placeholder="Enter your name to begin"
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && start()}
          aria-label="Your name"
          style={{ width: "100%", marginBottom: 18 }}
        />

        <div className="lang-row" role="group" aria-label="Choose a language">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              className={`lang-pill ${language === l.code ? "selected" : ""}`}
              onClick={() => setLanguage(l.code)}
              aria-pressed={language === l.code}
            >
              <span className="lang-flag">{l.flag}</span> {l.label}
            </button>
          ))}
        </div>

        <button
          className="primary"
          onClick={start}
          disabled={!ready}
          style={{ width: "100%", padding: "14px", fontSize: 16 }}
        >
          Start practicing
        </button>

        <p className="muted" style={{ marginTop: 14, fontSize: 13 }}>
          <a onClick={viewHistory} style={{ cursor: "pointer" }}>
            View history →
          </a>
        </p>

        <p className="muted" style={{ marginTop: 4, fontSize: 12 }}>
          Progress is saved per name and language — come back to pick up where you left off.
        </p>
      </div>
    </div>
  );
}
