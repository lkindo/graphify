# Web Visualizer

Interactive JavaScript code visualizer. Edit code, step through execution,
watch variables update, and analyze Big-O complexity — all in the browser.

## Features

- **Editable code** — CodeMirror 6 editor with JS syntax highlighting
- **Step through execution** — play, pause, step forward/back, scrub the timeline
- **Line-by-line highlighting** — the current line lights up as execution progresses
- **Call stack & variables** — see every frame's locals at every step
- **Heap visualization** — arrays as labeled cells, objects as key/value tables
- **Console output** — `console.log` output accumulates as you step
- **Big-O analysis** — sweep input sizes, plot operations vs. n, classify as O(1), O(log n), O(n), O(n log n), O(n²), O(n³), or O(2ⁿ)

## How it works

1. Source code is parsed with [acorn](https://github.com/acornjs/acorn) into an AST.
2. The AST is walked and every statement is instrumented with a `__trace(line, () => ({...locals}))` call. The closure captures the enclosing scope so the runtime can snapshot live variables.
3. The instrumented code runs once via `new Function()` — the runtime records a `Trace`, an ordered list of `Step` snapshots.
4. The UI is a pure function of `trace[currentStep]`. Scrubbing, play/pause, and step-back are free from this design.

## Running locally

```bash
cd web-visualizer
npm install
npm run dev          # http://localhost:5173
npm run build        # produces dist/
```

## Safety

- All execution happens on the main thread with a `MAX_STEPS=50_000` cap and a 3-second timeout, so infinite loops can't hang the page.
- Code runs in strict mode with a scrubbed `console` shim — no DOM, no fetch, no network.
- No user code ever leaves the browser.

## Supported JS subset

Full ES2022 parsing via acorn. The instrumenter handles:

- Statements: `var`/`let`/`const`, `if`/`else`, `while`, `do/while`, `for`, `for...of`, `for...in`, `return`, `throw`, `try/catch/finally`, `switch`.
- Expressions: any valid JS expression (arithmetic, comparison, logical, arrow fns, destructuring, spread/rest, template literals, optional chaining).
- Functions: declarations, expressions, arrows (with or without block body), recursion, closures.
- Builtins: `Math`, `JSON`, `Array`, `Object`, `Map`, `Set`, and their methods.

Blocked (by the `new Function` sandbox + lack of globals): `fetch`, `XMLHttpRequest`, DOM, `import`, timers.

## Presets

- **Bubble Sort** — O(n²)
- **Binary Search** — O(log n)
- **Fibonacci (recursive)** — O(2ⁿ)
- **Linear Sum** — O(n)

## Architecture

```
web-visualizer/
├── src/
│   ├── lib/
│   │   ├── types.ts         Value, HeapObject, Step, Trace types
│   │   ├── instrument.ts    acorn parse + AST instrumentation
│   │   ├── snapshot.ts      Cycle-safe value serializer
│   │   ├── runtime.ts       __trace/__enterFrame/__exitFrame implementations
│   │   ├── runner.ts        parse + execute wrapper
│   │   ├── classify.ts      n-sweep + Big-O classifier
│   │   └── presets.ts       Preset algorithms
│   ├── components/
│   │   ├── CodeEditor.tsx         CodeMirror wrapper + line decoration
│   │   ├── PlaybackControls.tsx   play/pause/step/scrub/speed
│   │   ├── ScopeViewer.tsx        call stack + locals
│   │   ├── HeapViewer.tsx         routes to ArrayViz/ObjectViz
│   │   ├── ArrayViz.tsx           boxes with index labels
│   │   ├── ObjectViz.tsx          key/value table
│   │   ├── ValuePill.tsx          compact single-value rendering
│   │   ├── ConsoleOutput.tsx      console.log output
│   │   └── ComplexityChart.tsx    SVG ops-vs-n chart + O(·) label
│   ├── App.tsx              Top-level orchestrator
│   ├── main.tsx             React entry point
│   └── styles.css           Dark theme
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## License

Same as graphify (see `../LICENSE`).
