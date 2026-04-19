import type { Value } from "../lib/types";
import { ValuePill } from "./ValuePill";

type Props = {
  entries: Array<[string, Value]>;
  heap: Record<number, { kind: string }>;
};

export function ObjectViz({ entries, heap }: Props) {
  if (entries.length === 0) {
    return <div className="object-empty">{"{ }"}</div>;
  }
  return (
    <table className="object-viz">
      <tbody>
        {entries.map(([key, val]) => (
          <tr key={key}>
            <td className="object-key">{key}</td>
            <td className="object-value">
              <ValuePill value={val} heap={heap} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
