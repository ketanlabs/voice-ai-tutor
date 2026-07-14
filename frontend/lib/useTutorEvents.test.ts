import { describe, expect, it } from "vitest";
import {
  initialTutorState,
  parseTutorEvent,
  tutorReducer,
  type TutorEvent,
} from "./tutorEvents";

const enc = (obj: unknown) => new TextEncoder().encode(JSON.stringify(obj));

const item = (over = {}) => ({
  image: "/flashcards/apple.jpg",
  emoji: "🍎",
  prompt_en: "apple",
  prompt_target: "manzana",
  index: 1,
  total: 10,
  ...over,
});

describe("parseTutorEvent", () => {
  it("decodes a valid item event from bytes", () => {
    const ev = parseTutorEvent(enc({ type: "item", data: item() }));
    expect(ev?.type).toBe("item");
  });

  it("decodes from a string payload too", () => {
    const ev = parseTutorEvent(JSON.stringify({ type: "exercise_end", data: { correct: 8, total: 10 } }));
    expect(ev?.type).toBe("exercise_end");
  });

  it("rejects unknown types and malformed json", () => {
    expect(parseTutorEvent(enc({ type: "nope", data: {} }))).toBeNull();
    expect(parseTutorEvent(enc({ data: {} }))).toBeNull();
    expect(parseTutorEvent("{not json")).toBeNull();
  });
});

describe("tutorReducer", () => {
  it("shows an item and resets its result", () => {
    const s = tutorReducer(initialTutorState, { type: "item", data: item() });
    expect(s.item?.prompt_target).toBe("manzana");
    expect(s.item?.result).toBeNull();
    expect(s.total).toBe(10);
  });

  it("marks 👍 / 👎 on the current item", () => {
    let s = tutorReducer(initialTutorState, { type: "item", data: item() });
    s = tutorReducer(s, { type: "item_result", data: { passed: true } });
    expect(s.item?.result).toBe("up");
    s = tutorReducer(s, { type: "item_result", data: { passed: false, tip: "try softer" } });
    expect(s.item?.result).toBe("down");
    expect(s.tip).toBe("try softer");
  });

  it("captures the final score and clears the card", () => {
    let s = tutorReducer(initialTutorState, { type: "item", data: item() });
    s = tutorReducer(s, { type: "exercise_end", data: { correct: 8, total: 10 } });
    expect(s.done).toEqual({ correct: 8, total: 10 });
    expect(s.item).toBeNull();
  });

  it("captures a fatal error event", () => {
    const ev = parseTutorEvent(enc({ type: "error", data: { message: "quota exceeded", fatal: true } }));
    const s = tutorReducer(initialTutorState, ev as TutorEvent);
    expect(s.error).toEqual({ message: "quota exceeded", fatal: true });
  });
});
