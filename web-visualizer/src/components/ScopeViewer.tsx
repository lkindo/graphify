import type { Step } from "../lib/types";
import { ValuePill } from "./ValuePill";

type Props = {
  step: Step;
};

export function ScopeViewer({ step }: Props) {
  return (
    <div className="scope-viewer">
      <h3 className="panel-title">Call Stack & Variables</h3>
      {step.stack.length === 0 && (
        <div className="panel-empty">(no frames)</div>
      )}
      {step.stack
        .slice()
        .reverse()
        .map((frame, idx) => {
          const entries = Object.entries(frame.locals);
          return (
            <div key={step.stack.length - idx - 1} className="frame">
              <div className="frame-header">
                <span className="frame-name">{frame.name}</span>
                {idx === 0 && <span className="frame-badge">current</span>}
              </div>
              {entries.length === 0 ? (
                <div className="frame-empty">(no locals)</div>
              ) : (
                <table className="frame-locals">
                  <tbody>
                    {entries.map(([name, val]) => (
                      <tr key={name}>
                        <td className="local-name">{name}</td>
                        <td className="local-value">
                          <ValuePill value={val} heap={step.heap} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
    </div>
  );
}
