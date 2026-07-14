"use client";

/** A small loading indicator used whenever we're waiting on the backend. */
export function Spinner({ label, small }: { label?: string; small?: boolean }) {
  return (
    <div className="loading-block">
      <div className={`spinner ${small ? "small" : ""}`} role="status" aria-label={label || "Loading"} />
      {label && <span>{label}</span>}
    </div>
  );
}
