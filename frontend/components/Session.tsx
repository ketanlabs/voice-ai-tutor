"use client";

import { LiveKitRoom } from "@livekit/components-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { fetchConnectionDetails, type ConnectionDetails, type Language } from "@/lib/api";
import { PracticeRoom } from "./PracticeRoom";
import { Spinner } from "./Spinner";

const HANDLE_KEY = "lingua.handle";
const LANG_KEY = "lingua.language";

export function Session() {
  const router = useRouter();
  const [details, setDetails] = useState<ConnectionDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // guard against double-invoke in StrictMode
    started.current = true;

    const handle = window.localStorage.getItem(HANDLE_KEY)?.trim();
    if (!handle) {
      router.replace("/");
      return;
    }
    const language = (window.localStorage.getItem(LANG_KEY) as Language) || "es";
    fetchConnectionDetails(handle, language)
      .then(setDetails)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to connect to Lingua."),
      );
  }, [router]);

  const goHome = () => router.push("/");

  if (error) {
    return (
      <div className="hero">
        <div className="hero-card">
          <h1>Couldn’t connect</h1>
          <p className="error">{error}</p>
          <button className="primary" onClick={goHome}>
            Back
          </button>
        </div>
      </div>
    );
  }

  if (!details) {
    return (
      <div className="hero">
        <div className="hero-card">
          <div className="flag">🗣️</div>
          <Spinner label="Connecting to Lingua…" />
        </div>
      </div>
    );
  }

  return (
    <LiveKitRoom
      token={details.token}
      serverUrl={details.livekit_url}
      connect
      audio={false}         /* mic is controlled solely by push-to-talk */
      video={false}
      onDisconnected={goHome}
    >
      <PracticeRoom details={details} onLeave={goHome} />
    </LiveKitRoom>
  );
}
