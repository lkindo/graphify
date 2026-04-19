import type { Step } from "../lib/types";
import { ArrayViz } from "./ArrayViz";
import { ObjectViz } from "./ObjectViz";

type Props = {
  step: Step;
};

export function HeapViewer({ step }: Props) {
  const heapIds = Object.keys(step.heap)
    .map(Number)
    .sort((a, b) => a - b);

  // Only show arrays and objects (not functions) — functions are just ƒ pills
  const displayable = heapIds.filter((id) => {
    const obj = step.heap[id];
    return obj && (obj.kind === "array" || obj.kind === "object");
  });

  return (
    <div className="heap-viewer">
      <h3 className="panel-title">Heap</h3>
      {displayable.length === 0 && (
        <div className="panel-empty">(no arrays or objects yet)</div>
      )}
      {displayable.map((id) => {
        const obj = step.heap[id];
        return (
          <div key={id} className="heap-entry">
            <div className="heap-entry-label">
              <span className="heap-badge">#{id}</span>
              <span className="heap-kind">{obj.kind}</span>
            </div>
            {obj.kind === "array" && (
              <ArrayViz items={obj.items} heap={step.heap} />
            )}
            {obj.kind === "object" && (
              <ObjectViz entries={obj.entries} heap={step.heap} />
            )}
          </div>
        );
      })}
    </div>
  );
}
