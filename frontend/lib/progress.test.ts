import { describe, it, expect } from "vitest";

import { scorePercent, formatLastPracticed } from "./progress";

describe("scorePercent", () => {
  it("computes a whole-number percentage", () => {
    expect(scorePercent(6, 10)).toBe(60);
  });

  it("rounds to the nearest percent", () => {
    expect(scorePercent(1, 3)).toBe(33);
    expect(scorePercent(2, 3)).toBe(67);
  });

  it("is 0 (not NaN) when there are no items", () => {
    expect(scorePercent(0, 0)).toBe(0);
  });

  it("is 100 for a perfect score", () => {
    expect(scorePercent(10, 10)).toBe(100);
  });
});

describe("formatLastPracticed", () => {
  it("returns null when never practiced (0)", () => {
    expect(formatLastPracticed(0)).toBeNull();
  });

  it("returns a non-null string for a real timestamp", () => {
    const out = formatLastPracticed(1_784_000_000);
    expect(out).not.toBeNull();
    expect(typeof out).toBe("string");
    expect((out as string).length).toBeGreaterThan(0);
  });
});
