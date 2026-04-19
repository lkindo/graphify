import type { Value } from "../lib/types";
import { ValuePill } from "./ValuePill";

type Props = {
  items: Value[];
  heap: Record<number, { kind: string }>;
};

export function ArrayViz({ items, heap }: Props) {
  if (items.length === 0) {
    return <div className="array-empty">[ ]</div>;
  }
  return (
    <div className="array-viz">
      {items.map((item, i) => (
        <div key={i} className="array-cell">
          <div className="array-value">
            <ValuePill value={item} heap={heap} />
          </div>
          <div className="array-index">{i}</div>
        </div>
      ))}
    </div>
  );
}
