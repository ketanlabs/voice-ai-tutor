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
