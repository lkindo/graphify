import type { Value } from "../lib/types";

type Props = {
  value: Value;
  heap: Record<number, { kind: string }>;
};

/** Compact one-line rendering of any Value — primitives inline, refs as link pills. */
export function ValuePill({ value, heap }: Props) {
  if (value.kind === "primitive") {
    if (value.type === "string") {
      return <span className="val val-string">{JSON.stringify(value.value)}</span>;
    }
    if (value.type === "null") return <span className="val val-null">null</span>;
    if (value.type === "undefined")
      return <span className="val val-undef">undefined</span>;
    if (value.type === "number")
      return <span className="val val-number">{String(value.value)}</span>;
    if (value.type === "boolean")
      return <span className="val val-bool">{String(value.value)}</span>;
  }
  if (value.kind !== "ref") return null;
  const id = value.id;
  const obj = heap[id];
  if (!obj) return <span className="val val-ref">#{id}</span>;
  if (obj.kind === "array")
    return <span className="val val-ref">→ array #{id}</span>;
  if (obj.kind === "object")
    return <span className="val val-ref">→ object #{id}</span>;
  if (obj.kind === "function")
    return <span className="val val-fn">ƒ #{id}</span>;
  return <span className="val val-ref">#{id}</span>;
}
