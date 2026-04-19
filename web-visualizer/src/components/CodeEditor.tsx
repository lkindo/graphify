import CodeMirror from "@uiw/react-codemirror";
import { javascript } from "@codemirror/lang-javascript";
import { EditorView, Decoration, lineNumbers } from "@codemirror/view";
import { StateField, StateEffect, type Extension } from "@codemirror/state";
import { useMemo } from "react";

// Effect and field for highlighting the current line
const setHighlightLine = StateEffect.define<number | null>();

const highlightLineField = StateField.define({
  create: () => Decoration.none,
  update(decos, tr) {
    decos = decos.map(tr.changes);
    for (const e of tr.effects) {
      if (e.is(setHighlightLine)) {
        const line = e.value;
        if (line == null) {
          decos = Decoration.none;
        } else {
          const doc = tr.state.doc;
          if (line >= 1 && line <= doc.lines) {
            const lineInfo = doc.line(line);
            decos = Decoration.set([
              Decoration.line({ class: "cm-current-line-highlight" }).range(
                lineInfo.from,
              ),
            ]);
          } else {
            decos = Decoration.none;
          }
        }
      }
    }
    return decos;
  },
  provide: (f) => EditorView.decorations.from(f),
});

type Props = {
  code: string;
  onCodeChange: (code: string) => void;
  /** Unused at render time — line highlight is dispatched via updateHighlight(). */
  highlightedLine?: number | null;
  editorViewRef?: (view: EditorView | null) => void;
};

export function CodeEditor({
  code,
  onCodeChange,
  editorViewRef,
}: Props) {
  const extensions: Extension[] = useMemo(
    () => [
      javascript(),
      lineNumbers(),
      highlightLineField,
      EditorView.theme({
        "&": { fontSize: "13px", backgroundColor: "transparent" },
        ".cm-scroller": { fontFamily: "var(--font-mono)" },
        ".cm-current-line-highlight": {
          backgroundColor: "rgba(217, 119, 6, 0.15)",
          borderLeft: "2px solid #d97706",
        },
        ".cm-gutters": {
          backgroundColor: "transparent",
          border: "none",
          color: "rgba(237, 237, 237, 0.3)",
        },
        "&.cm-focused": { outline: "none" },
      }),
    ],
    [],
  );

  return (
    <CodeMirror
      value={code}
      onChange={onCodeChange}
      extensions={extensions}
      theme="dark"
      basicSetup={{
        lineNumbers: false, // we add our own
        foldGutter: false,
        highlightActiveLine: false,
      }}
      onCreateEditor={(view) => {
        editorViewRef?.(view);
        // Expose effect via custom events
        (view as EditorView & { __setHighlight: typeof setHighlightLine }).__setHighlight =
          setHighlightLine;
      }}
      height="100%"
      style={{ height: "100%" }}
    />
  );
}

/** Dispatch highlight update to a view. Call from the orchestrator. */
export function updateHighlight(view: EditorView | null, line: number | null): void {
  if (!view) return;
  view.dispatch({ effects: setHighlightLine.of(line) });
}
