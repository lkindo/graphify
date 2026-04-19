/**
 * Runtime injected into instrumented code.
 *
 * The instrumenter generates:
 *   __trace(line, () => ({x, y, z}))       — one per statement
 *   __enterFrame(name, paramNames, paramValues)
 *   __exitFrame()
 *
 * This module builds those runtime functions and records a Trace.
 */
import { Serializer } from "./snapshot";
import type { Step, Trace, Value } from "./types";

type FrameRecord = {
  name: string;
  /** Snapshot function set by the closest __trace — captures visible vars. */
  getLocals: () => Record<string, unknown>;
  /** Initial params (used before first __trace in the frame). */
  paramValues: Record<string, unknown>;
};

export type RunOptions = {
  maxSteps: number;
  timeoutMs?: number;
};

export function runInstrumented(
  instrumentedCode: string,
  options: RunOptions
): Trace {
  const steps: Step[] = [];
  const output: string[] = [];
  const frames: FrameRecord[] = [
    {
      name: "<global>",
      getLocals: () => ({}),
      paramValues: {},
    },
  ];
  let ops = 0;
  let truncated = false;
  let error: string | null = null;

  const startTime = Date.now();
  const timeoutMs = options.timeoutMs ?? 3000;

  const takeSnapshot = (line: number): void => {
    if (steps.length >= options.maxSteps) {
      truncated = true;
      throw new Error("__MAX_STEPS__");
    }
    if (Date.now() - startTime > timeoutMs) {
      truncated = true;
      throw new Error("__TIMEOUT__");
    }

    const serializer = new Serializer();
    const stackFrames = frames.map((f) => {
      let locals: Record<string, unknown> = {};
      try {
        locals = f.getLocals();
      } catch {
        // Locals may reference TDZ vars; fall back to params
        locals = f.paramValues;
      }
      return {
        name: f.name,
        locals: serializer.serializeLocals(locals),
      };
    });

    steps.push({
      line,
      stack: stackFrames,
      heap: serializer.getHeap(),
      output: [...output],
      ops,
    });
  };

  const __trace = (
    line: number,
    capture: () => Record<string, unknown>
  ): void => {
    // Update the top frame's captor so stack viewer has live locals.
    frames[frames.length - 1].getLocals = capture;
    ops++;
    takeSnapshot(line);
  };

  const __enterFrame = (
    name: string,
    paramNames: string[],
    paramValues: unknown[]
  ): void => {
    const params: Record<string, unknown> = {};
    for (let i = 0; i < paramNames.length; i++) {
      params[paramNames[i]] = paramValues[i];
    }
    frames.push({
      name,
      getLocals: () => params, // replaced by first __trace inside the function
      paramValues: params,
    });
  };

  const __exitFrame = (): void => {
    if (frames.length > 1) frames.pop();
  };

  const __log = (...args: unknown[]): void => {
    output.push(args.map((a) => formatForLog(a)).join(" "));
  };

  const __op = (): void => {
    ops++;
  };

  const sandboxedConsole = {
    log: __log,
    warn: __log,
    error: __log,
    info: __log,
  };

  try {
    // eslint-disable-next-line @typescript-eslint/no-implied-eval
    const fn = new Function(
      "__trace",
      "__op",
      "__enterFrame",
      "__exitFrame",
      "__log",
      "console",
      `"use strict";\n${instrumentedCode}`
    );
    fn(__trace, __op, __enterFrame, __exitFrame, __log, sandboxedConsole);

    // Final snapshot so the last statement's output + state are captured.
    try {
      const lastLine = steps.length > 0 ? steps[steps.length - 1].line : 0;
      takeSnapshot(lastLine);
    } catch {
      // MAX_STEPS or TIMEOUT hit — ignore
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg !== "__MAX_STEPS__" && msg !== "__TIMEOUT__") {
      error = msg;
    }
  }

  return {
    steps,
    truncated,
    error,
    finalOps: ops,
  };
}

function formatForLog(v: unknown): string {
  if (v === null) return "null";
  if (v === undefined) return "undefined";
  const t = typeof v;
  if (t === "string") return v as string;
  if (t === "number" || t === "boolean") return String(v);
  if (t === "function") return `[Function: ${(v as { name?: string }).name || "anon"}]`;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

export function valueToString(
  v: Value,
  heap: Record<number, { kind: string }>
): string {
  if (v.kind === "primitive") {
    if (v.type === "string") return JSON.stringify(v.value);
    if (v.type === "null") return "null";
    if (v.type === "undefined") return "undefined";
    return String(v.value);
  }
  const obj = heap[v.id];
  if (!obj) return `#${v.id}`;
  if (obj.kind === "array") return `Array#${v.id}`;
  if (obj.kind === "object") return `Object#${v.id}`;
  if (obj.kind === "function") return `ƒ #${v.id}`;
  return `#${v.id}`;
}
