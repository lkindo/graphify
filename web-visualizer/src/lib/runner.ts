/**
 * Main-thread runner: parse → instrument → execute → return Trace.
 *
 * Runs synchronously on the caller's thread. For DSA snippets with
 * MAX_STEPS=50k this is fine; the UI debounces re-traces so it doesn't
 * thrash during typing.
 */
import { instrument } from "./instrument";
import { runInstrumented } from "./runtime";
import type { Trace } from "./types";

export const DEFAULT_MAX_STEPS = 50_000;
export const DEFAULT_TIMEOUT_MS = 3_000;

export type RunOptions = {
  maxSteps?: number;
  timeoutMs?: number;
};

/** Compile + run source. Catches syntax errors and returns them in trace.error. */
export function trace(source: string, options: RunOptions = {}): Trace {
  let instrumented: string;
  try {
    instrumented = instrument(source).code;
  } catch (e) {
    return {
      steps: [],
      truncated: false,
      error: e instanceof Error ? e.message : String(e),
      finalOps: 0,
    };
  }

  return runInstrumented(instrumented, {
    maxSteps: options.maxSteps ?? DEFAULT_MAX_STEPS,
    timeoutMs: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  });
}
