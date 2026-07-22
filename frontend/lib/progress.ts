// Pure helpers for the lesson-history view — no React, no fetch, so they are
// trivially unit-testable (see progress.test.ts).

/** Whole-percent score, guarding divide-by-zero (0 items → 0%). */
export function scorePercent(passed: number, total: number): number {
  return total > 0 ? Math.round((passed / total) * 100) : 0;
}

/** Format a unix-seconds timestamp as a human "last practiced" string, or null
 *  when the learner has never practiced (timestamp is 0 / missing). */
export function formatLastPracticed(unixSeconds: number): string | null {
  if (!unixSeconds) return null;
  return new Date(unixSeconds * 1000).toLocaleString();
}
