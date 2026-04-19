import type { ComplexityResult } from "../lib/classify";

type Props = {
  result: ComplexityResult | null;
  isMeasuring: boolean;
};

/** SVG chart: operations (y) vs n (x), with O-class label. */
export function ComplexityChart({ result, isMeasuring }: Props) {
  if (isMeasuring) {
    return (
      <div className="complexity-chart">
        <h3 className="panel-title">Complexity</h3>
        <div className="panel-empty">measuring…</div>
      </div>
    );
  }

  if (!result || result.samples.length < 2) {
    return (
      <div className="complexity-chart">
        <h3 className="panel-title">Complexity</h3>
        <div className="panel-empty">
          Click &ldquo;Analyze complexity&rdquo; to measure Big-O.
        </div>
      </div>
    );
  }

  const width = 320;
  const height = 180;
  const padL = 40;
  const padR = 12;
  const padT = 12;
  const padB = 28;

  const maxN = Math.max(...result.samples.map((s) => s.n));
  const maxOps = Math.max(...result.samples.map((s) => s.ops));

  const xScale = (n: number) => padL + ((n / maxN) * (width - padL - padR));
  const yScale = (ops: number) =>
    height - padB - ((ops / Math.max(1, maxOps)) * (height - padT - padB));

  const path = result.samples
    .map((s, i) => `${i === 0 ? "M" : "L"} ${xScale(s.n).toFixed(1)} ${yScale(s.ops).toFixed(1)}`)
    .join(" ");

  const confidencePct = Math.round(result.confidence * 100);

  return (
    <div className="complexity-chart">
      <h3 className="panel-title">Complexity</h3>
      <div className="complexity-label">
        <span className="complexity-class">{result.class}</span>
        <span className="complexity-confidence">{confidencePct}% confidence</span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        className="chart-svg"
      >
        {/* Axes */}
        <line
          x1={padL}
          y1={height - padB}
          x2={width - padR}
          y2={height - padB}
          stroke="rgba(237,237,237,0.2)"
        />
        <line
          x1={padL}
          y1={padT}
          x2={padL}
          y2={height - padB}
          stroke="rgba(237,237,237,0.2)"
        />
        {/* Path */}
        <path d={path} fill="none" stroke="#d97706" strokeWidth="2" />
        {/* Points */}
        {result.samples.map((s, i) => (
          <circle
            key={i}
            cx={xScale(s.n)}
            cy={yScale(s.ops)}
            r="3"
            fill="#d97706"
          />
        ))}
        {/* Axis labels */}
        <text
          x={width / 2}
          y={height - 6}
          textAnchor="middle"
          fontSize="10"
          fill="rgba(237,237,237,0.5)"
        >
          input size (n)
        </text>
        <text
          x={12}
          y={padT + 4}
          fontSize="10"
          fill="rgba(237,237,237,0.5)"
        >
          ops
        </text>
        {/* Tick labels */}
        <text
          x={padL}
          y={height - padB + 14}
          textAnchor="middle"
          fontSize="9"
          fill="rgba(237,237,237,0.4)"
        >
          0
        </text>
        <text
          x={width - padR}
          y={height - padB + 14}
          textAnchor="middle"
          fontSize="9"
          fill="rgba(237,237,237,0.4)"
        >
          {maxN}
        </text>
        <text
          x={padL - 4}
          y={yScale(maxOps) + 3}
          textAnchor="end"
          fontSize="9"
          fill="rgba(237,237,237,0.4)"
        >
          {maxOps}
        </text>
      </svg>
      <table className="sample-table">
        <thead>
          <tr>
            <th>n</th>
            <th>ops</th>
          </tr>
        </thead>
        <tbody>
          {result.samples.map((s) => (
            <tr key={s.n}>
              <td>{s.n}</td>
              <td>{s.ops.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
