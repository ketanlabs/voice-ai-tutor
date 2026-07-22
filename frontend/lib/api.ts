// Talks to the BACKEND for connection details. The frontend never holds
// LiveKit secrets — the backend mints the token from the learner's handle.

export type Language = "es" | "fr" | "it";

export interface ConnectionDetails {
  token: string;
  livekit_url: string;
  identity: string;
  language: Language;
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function fetchConnectionDetails(
  handle: string,
  language: Language,
): Promise<ConnectionDetails> {
  const res = await fetch(`${BACKEND_URL}/session/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handle, language }),
  });
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

// ---- learner progress (lesson history) -----------------------------------
// Consumes GET /learners/{handle}:{lang}/progress — one row per curriculum
// item, joined with the learner's practice record, plus a mastery score.

export interface WordProgress {
  prompt: string; // English prompt (canonical, from the curriculum)
  word: string; // target-language translation, "" until practiced
  seen: number;
  correct: number;
  passed: boolean; // ever correct at least once (attempts earn no credit)
}

export interface ProgressProfile {
  cefr_level: string;
  native_lang: string;
  target_lang: string;
  created_at: number;
  last_seen: number; // unix seconds
}

export interface LearnerProgress {
  identity: string;
  language: Language;
  profile: ProgressProfile;
  items: WordProgress[];
  score: { passed: number; total: number };
}

export async function fetchProgress(
  handle: string,
  language: Language,
): Promise<LearnerProgress> {
  // Identity is per-language ({handle}:{lang}); encode so names with spaces or
  // the ':' separator survive the URL (Starlette decodes it back for the route).
  const identity = encodeURIComponent(`${handle}:${language}`);
  const res = await fetch(`${BACKEND_URL}/learners/${identity}/progress`);
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}: ${await res.text()}`);
  }
  return res.json();
}
