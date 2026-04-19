/**
 * Core types for the code visualizer.
 *
 * A trace is an ordered list of Steps produced by running instrumented source code
 * once. Each Step is a snapshot of the program state at a statement boundary.
 * The UI is a pure function of `trace[currentStep]`.
 */

/** A single JS value serialized for display. Objects/arrays become HeapRef. */
export type Value =
  | { kind: "primitive"; type: "number" | "string" | "boolean" | "null" | "undefined"; value: string | number | boolean | null }
  | { kind: "ref"; id: number };

/** A heap object — arrays and plain objects get hoisted here to preserve identity. */
export type HeapObject =
  | { kind: "array"; id: number; items: Value[] }
  | { kind: "object"; id: number; entries: Array<[string, Value]> }
  | { kind: "function"; id: number; name: string };

/** A stack frame — represents one function call's local scope. */
export type Frame = {
  /** Function name (or "<global>" for top-level). */
  name: string;
  /** Local variables in this frame. */
  locals: Record<string, Value>;
};

/** One snapshot of program state. */
export type Step = {
  /** 1-indexed source line currently executing. */
  line: number;
  /** Call stack, top = most recent frame. */
  stack: Frame[];
  /** Heap — referenced by HeapRef ids. */
  heap: Record<number, HeapObject>;
  /** Console output accumulated so far (appended per log). */
  output: string[];
  /** Total operations executed so far (for complexity analysis). */
  ops: number;
};

export type Trace = {
  steps: Step[];
  truncated: boolean;
  error: string | null;
  finalOps: number;
};

/** Message sent to the worker to run code. */
export type RunRequest = {
  type: "run";
  code: string;
  maxSteps: number;
};

/** Messages from worker back to main. */
export type RunResponse =
  | { type: "ok"; trace: Trace }
  | { type: "error"; message: string };
