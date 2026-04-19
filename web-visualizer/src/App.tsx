import { useEffect, useMemo, useRef, useState } from "react";
import type { EditorView } from "@codemirror/view";

import { trace } from "./lib/runner";
import { measure, classify, type ComplexityResult } from "./lib/classify";
import { PRESETS } from "./lib/presets";
import type { Trace } from "./lib/types";

import { CodeEditor, updateHighlight } from "./components/CodeEditor";
import { PlaybackControls } from "./components/PlaybackControls";
import { ScopeViewer } from "./components/ScopeViewer";
import { HeapViewer } from "./components/HeapViewer";
import { ConsoleOutput } from "./components/ConsoleOutput";
import { ComplexityChart } from "./components/ComplexityChart";

const DEBOUNCE_MS = 400;

export function App() {
  const [code, setCode] = useState<string>(PRESETS[0].code);
  const [presetIdx, setPresetIdx] = useState<number>(0);
  const [traceResult, setTraceResult] = useState<Trace | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<number>(500);

  const [complexity, setComplexity] = useState<ComplexityResult | null>(null);
  const [isMeasuring, setIsMeasuring] = useState<boolean>(false);

  const editorViewRef = useRef<EditorView | null>(null);
  const debounceRef = useRef<number | null>(null);
  const playTimerRef = useRef<number | null>(null);

  // Re-trace on code change (debounced)
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      const t = trace(code);
      setTraceResult(t);
      setCurrentStep(0);
      setIsPlaying(false);
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [code]);

  // Initial trace on first mount
  useEffect(() => {
    const t = trace(code);
    setTraceResult(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Playback loop
  useEffect(() => {
    if (!isPlaying || !traceResult) return;
    playTimerRef.current = window.setTimeout(() => {
      setCurrentStep((s) => {
        const next = s + 1;
        if (next >= traceResult.steps.length) {
          setIsPlaying(false);
          return s;
        }
        return next;
      });
    }, speed);
    return () => {
      if (playTimerRef.current) window.clearTimeout(playTimerRef.current);
    };
  }, [isPlaying, currentStep, traceResult, speed]);

  // Update editor line highlight
  useEffect(() => {
    if (!traceResult || traceResult.steps.length === 0) {
      updateHighlight(editorViewRef.current, null);
      return;
    }
    const step = traceResult.steps[currentStep];
    updateHighlight(editorViewRef.current, step?.line ?? null);
  }, [traceResult, currentStep]);

  const step = traceResult?.steps[currentStep];
  const totalSteps = traceResult?.steps.length ?? 0;

  const handlePreset = (idx: number) => {
    setPresetIdx(idx);
    setCode(PRESETS[idx].code);
    setComplexity(null);
  };

  const handleMeasureComplexity = () => {
    const preset = PRESETS[presetIdx];
    setIsMeasuring(true);
    // yield to paint
    setTimeout(() => {
      const samples = measure(preset.complexityTemplate);
      const result = classify(samples);
      setComplexity(result);
      setIsMeasuring(false);
    }, 10);
  };

  const status = useMemo(() => {
    if (!traceResult) return { kind: "loading" as const };
    if (traceResult.error) return { kind: "error" as const, msg: traceResult.error };
    if (traceResult.truncated)
      return { kind: "warning" as const, msg: `Truncated after ${totalSteps} steps.` };
    if (totalSteps === 0) return { kind: "empty" as const };
    return { kind: "ok" as const, msg: `${totalSteps} steps, ${traceResult.finalOps} ops` };
  }, [traceResult, totalSteps]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-title">
          <h1>Code Visualizer</h1>
          <p className="app-subtitle">
            Step through JS execution · inspect memory · analyze Big-O
          </p>
        </div>
        <div className="preset-bar">
          <label htmlFor="preset-select" className="preset-label">preset:</label>
          <select
            id="preset-select"
            value={presetIdx}
            onChange={(e) => handlePreset(Number(e.target.value))}
            className="preset-select"
          >
            {PRESETS.map((p, i) => (
              <option key={i} value={i}>
                {p.name} · {p.complexity}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="app-body">
        {/* Left: editor + controls */}
        <section className="pane pane-editor">
          <div className="pane-header">
            <h2 className="pane-title">Code</h2>
            <span className={`status-badge status-${status.kind}`}>
              {status.kind === "ok" && status.msg}
              {status.kind === "error" && `Error: ${status.msg}`}
              {status.kind === "warning" && status.msg}
              {status.kind === "empty" && "No executable code"}
              {status.kind === "loading" && "Parsing…"}
            </span>
          </div>
          <div className="editor-container">
            <CodeEditor
              code={code}
              onCodeChange={setCode}
              highlightedLine={step?.line ?? null}
              editorViewRef={(v) => {
                editorViewRef.current = v;
              }}
            />
          </div>
          <PlaybackControls
            currentStep={currentStep}
            totalSteps={totalSteps}
            isPlaying={isPlaying}
            speed={speed}
            onPlayPause={() => setIsPlaying((p) => !p)}
            onStepBack={() => setCurrentStep((s) => Math.max(0, s - 1))}
            onStepForward={() =>
              setCurrentStep((s) => Math.min(totalSteps - 1, s + 1))
            }
            onReset={() => {
              setCurrentStep(0);
              setIsPlaying(false);
            }}
            onScrub={setCurrentStep}
            onSpeedChange={setSpeed}
          />
        </section>

        {/* Right: state panels */}
        <section className="pane pane-state">
          {step ? (
            <>
              <div className="panel">
                <ScopeViewer step={step} />
              </div>
              <div className="panel">
                <HeapViewer step={step} />
              </div>
              <div className="panel">
                <ConsoleOutput output={step.output} />
              </div>
            </>
          ) : (
            <div className="panel">
              <div className="panel-empty">
                {traceResult?.error
                  ? `Syntax error: ${traceResult.error}`
                  : "Edit code to begin."}
              </div>
            </div>
          )}

          <div className="panel">
            <div className="complexity-actions">
              <button
                onClick={handleMeasureComplexity}
                disabled={isMeasuring}
                className="btn btn-secondary"
              >
                {isMeasuring ? "Measuring…" : "Analyze complexity"}
              </button>
              <span className="complexity-hint">
                Expected: <strong>{PRESETS[presetIdx].complexity}</strong>
              </span>
            </div>
            <ComplexityChart result={complexity} isMeasuring={isMeasuring} />
          </div>
        </section>
      </div>

      <footer className="app-footer">
        <span>
          Part of{" "}
          <a
            href="https://github.com/safishamsi/graphify"
            target="_blank"
            rel="noopener noreferrer"
          >
            graphify
          </a>
          . Built with acorn, CodeMirror, and React.
        </span>
      </footer>
    </div>
  );
}
