type Props = {
  output: string[];
};

export function ConsoleOutput({ output }: Props) {
  return (
    <div className="console-output">
      <h3 className="panel-title">Console</h3>
      {output.length === 0 ? (
        <div className="panel-empty">(no output yet)</div>
      ) : (
        <div className="console-lines">
          {output.map((line, i) => (
            <div key={i} className="console-line">
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
