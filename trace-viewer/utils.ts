import { TraceEvent } from "./types";

/**
 * Normalizes trace events from old format (llm_call) to new format (agent_step/validator_step)
 * This provides backward compatibility for traces using the old format.
 */
export function normalizeTraceEvents(events: TraceEvent[]): TraceEvent[] {
  return events.map((event) => {
    // If already in new format, return as-is
    if (event.event === "agent_step" || event.event === "validator_step") {
      return event;
    }

    // Convert old "llm_call" format
    if (event.event === "llm_call") {
      const isValidator = event.context === "BullshitCaller";

      if (isValidator) {
        // Convert validator llm_call to validator_step
        return {
          ...event,
          event: "validator_step" as const,
          validator_name: "BullshitCaller",
          validation_passed: event.output?.is_valid ?? true,
          validates_node_id: event.parent_node_id || undefined,
        };
      } else {
        // Convert agent llm_call to agent_step
        return {
          ...event,
          event: "agent_step" as const,
        };
      }
    }

    // Unknown event type, return as-is
    return event;
  });
}

/**
 * Creates a lookup map from node_id to its validator event (if any)
 */
export function buildValidatorLookup(
  events: TraceEvent[]
): Map<string, TraceEvent> {
  const lookup = new Map<string, TraceEvent>();

  for (const event of events) {
    if (event.event === "validator_step" && event.validates_node_id) {
      lookup.set(event.validates_node_id, event);
    }
  }

  return lookup;
}

/**
 * Filters out validator events from the trace, returning only agent/orchestrator steps
 */
export function filterAgentSteps(events: TraceEvent[]): TraceEvent[] {
  return events.filter(
    (event) =>
      event.event !== "validator_step" && event.context !== "BullshitCaller"
  );
}

