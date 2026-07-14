"use client";

import type { TutorError } from "@/lib/tutorEvents";

export function ErrorBanner({
  error,
  onDismiss,
}: {
  error: TutorError;
  onDismiss: () => void;
}) {
  return (
    <div className={`error-banner ${error.fatal ? "fatal" : ""}`} role="alert">
      <span className="error-banner-icon">⚠️</span>
      <div className="error-banner-body">
        <strong>{error.fatal ? "The tutor stopped" : "Something went wrong"}</strong>
        <div>{error.message}</div>
      </div>
      <button className="error-banner-close" onClick={onDismiss} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
