// Pure logic for the exercise UI side-channel — no React, no LiveKit imports, so
// it is trivially unit-testable (see useTutorEvents.test.ts).

export const UI_TOPIC = "tutor-ui";

export interface ExerciseItem {
  image: string;
  emoji: string;
  prompt_en: string;
  prompt_target: string;
  index: number;
  total: number;
  result: "up" | "down" | null;
}

export interface TutorError {
  message: string;
  fatal: boolean;
}

export type TutorEvent =
  | { type: "exercise_start"; data: { total: number } }
  | {
      type: "item";
      data: {
        image: string;
        emoji: string;
        prompt_en: string;
        prompt_target: string;
        index: number;
        total: number;
      };
    }
  | { type: "item_result"; data: { passed: boolean; tip?: string } }
  | { type: "exercise_end"; data: { correct: number; total: number } }
  | { type: "error"; data: { message: string; fatal?: boolean } };

export interface TutorState {
  item: ExerciseItem | null;
  tip: string | null;
  total: number;
  done: { correct: number; total: number } | null;
  error: TutorError | null;
}

export const initialTutorState: TutorState = {
  item: null,
  tip: null,
  total: 0,
  done: null,
  error: null,
};

const KNOWN_TYPES = new Set([
  "exercise_start",
  "item",
  "item_result",
  "exercise_end",
  "error",
]);

/** Decode a data-channel payload (bytes or string) into a validated TutorEvent. */
export function parseTutorEvent(payload: Uint8Array | string): TutorEvent | null {
  try {
    const text =
      typeof payload === "string" ? payload : new TextDecoder().decode(payload);
    const obj = JSON.parse(text);
    if (
      obj &&
      typeof obj.type === "string" &&
      KNOWN_TYPES.has(obj.type) &&
      typeof obj.data === "object" &&
      obj.data !== null
    ) {
      return obj as TutorEvent;
    }
    return null;
  } catch {
    return null;
  }
}

/** Fold an event into UI state. Pure — returns a new state object. */
export function tutorReducer(state: TutorState, event: TutorEvent): TutorState {
  switch (event.type) {
    case "exercise_start":
      return { ...initialTutorState, total: event.data.total };
    case "item":
      return {
        ...state,
        done: null,
        tip: null,
        total: event.data.total || state.total,
        item: { ...event.data, result: null },
      };
    case "item_result":
      return {
        ...state,
        tip: event.data.tip || null,
        item: state.item
          ? { ...state.item, result: event.data.passed ? "up" : "down" }
          : state.item,
      };
    case "exercise_end":
      return { ...state, done: { correct: event.data.correct, total: event.data.total }, item: null };
    case "error":
      return { ...state, error: { message: event.data.message, fatal: !!event.data.fatal } };
    default:
      return state;
  }
}
