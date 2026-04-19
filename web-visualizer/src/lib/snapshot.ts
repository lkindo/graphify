/**
 * Serialize a live JS value into the visualizer's Value / HeapObject format.
 * Handles primitives, arrays, plain objects, and functions. Cycle-safe.
 */
import type { Value, HeapObject } from "./types";

export class Serializer {
  private heap: Record<number, HeapObject> = {};
  private seen = new WeakMap<object, number>();
  private nextId = 1;

  /** Serialize a value. Mutates internal heap. */
  serialize(v: unknown): Value {
    if (v === null) {
      return { kind: "primitive", type: "null", value: null };
    }
    if (v === undefined) {
      return { kind: "primitive", type: "undefined", value: null };
    }
    const t = typeof v;
    if (t === "number" || t === "boolean") {
      return { kind: "primitive", type: t, value: v as number | boolean };
    }
    if (t === "string") {
      // Truncate huge strings
      const s = v as string;
      return {
        kind: "primitive",
        type: "string",
        value: s.length > 200 ? s.slice(0, 200) + "…" : s,
      };
    }
    if (t === "function") {
      const fn = v as { name?: string };
      const id = this.getOrCreateId(v as object);
      if (!this.heap[id]) {
        this.heap[id] = { kind: "function", id, name: fn.name || "<anon>" };
      }
      return { kind: "ref", id };
    }
    if (t === "object") {
      const id = this.getOrCreateId(v as object);
      if (this.heap[id]) {
        return { kind: "ref", id };
      }
      if (Array.isArray(v)) {
        // Pre-register to handle cycles
        this.heap[id] = { kind: "array", id, items: [] };
        const items = (v as unknown[]).map((item) => this.serialize(item));
        this.heap[id] = { kind: "array", id, items };
        return { kind: "ref", id };
      }
      // Plain object
      this.heap[id] = { kind: "object", id, entries: [] };
      const entries: Array<[string, Value]> = [];
      for (const key of Object.keys(v as Record<string, unknown>)) {
        entries.push([key, this.serialize((v as Record<string, unknown>)[key])]);
      }
      this.heap[id] = { kind: "object", id, entries };
      return { kind: "ref", id };
    }
    // Fallback — treat unknowns (bigint, symbol) as string
    return { kind: "primitive", type: "string", value: String(v) };
  }

  /** Snapshot locals (Record<name, rawValue>) into Record<name, Value>. */
  serializeLocals(locals: Record<string, unknown>): Record<string, Value> {
    const out: Record<string, Value> = {};
    for (const k of Object.keys(locals)) {
      out[k] = this.serialize(locals[k]);
    }
    return out;
  }

  /** Get the accumulated heap snapshot. Clones so further mutations don't leak. */
  getHeap(): Record<number, HeapObject> {
    // Deep-ish clone — each HeapObject is already serialized, so a shallow
    // copy of the record + each entry is enough.
    const cloned: Record<number, HeapObject> = {};
    for (const id of Object.keys(this.heap)) {
      const obj = this.heap[Number(id)];
      if (obj.kind === "array") {
        cloned[obj.id] = { kind: "array", id: obj.id, items: [...obj.items] };
      } else if (obj.kind === "object") {
        cloned[obj.id] = {
          kind: "object",
          id: obj.id,
          entries: obj.entries.map(([k, val]) => [k, val]),
        };
      } else {
        cloned[obj.id] = { ...obj };
      }
    }
    return cloned;
  }

  /** Reset for a fresh snapshot (call between steps). */
  reset(): void {
    this.heap = {};
    this.seen = new WeakMap();
    this.nextId = 1;
  }

  private getOrCreateId(obj: object): number {
    let id = this.seen.get(obj);
    if (id === undefined) {
      id = this.nextId++;
      this.seen.set(obj, id);
    }
    return id;
  }
}
