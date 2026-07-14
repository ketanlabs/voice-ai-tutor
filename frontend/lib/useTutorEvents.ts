"use client";

import { useReducer } from "react";
import { useDataChannel } from "@livekit/components-react";
import {
  UI_TOPIC,
  initialTutorState,
  parseTutorEvent,
  tutorReducer,
  type TutorState,
} from "./tutorEvents";

/**
 * Subscribe to the agent's `tutor-ui` data channel and fold incoming events
 * into UI state. All decoding/reducing logic lives in tutorEvents.ts (pure +
 * unit-tested); this hook just wires it to LiveKit + React.
 */
export function useTutorEvents(initial?: Partial<TutorState>): TutorState {
  const [state, dispatch] = useReducer(tutorReducer, {
    ...initialTutorState,
    ...initial,
  });

  useDataChannel(UI_TOPIC, (msg) => {
    const event = parseTutorEvent(msg.payload);
    if (event) dispatch(event);
  });

  return state;
}
