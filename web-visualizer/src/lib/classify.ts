/**
 * Complexity classifier: run instrumented code against varying input sizes,
 * record operation counts, and fit the (n, ops) curve to a known O(·) class.
 */
import { trace } from "./runner";

export type ComplexityClass =
  | "O(1)"
  | "O(log n)"
  | "O(n)"
  | "O(n log n)"
  | "O(n²)"
  | "O(n³)"
  | "O(2^n)"
  | "unknown";

export type Sample = { n: number; ops: number };

export type ComplexityResult = {
  samples: Sample[];
  class: ComplexityClass;
  /** How well the best-fit curve matches (0-1, higher = better). */
  confidence: number;
};

/**
 * Measure ops for a code template across several input sizes.
 *
 * The user provides a template where `{n}` is replaced with the size.
 * Example template:
 *   const arr = Array.from({length: {n}}, (_, i) => {n} - i);
 *   bubbleSort(arr);
 */
export function measure(
  codeTemplate: string,
  sizes: number[] = [10, 25, 50, 100, 200, 400]
): Sample[] {
  const samples: Sample[] = [];
  for (const n of sizes) {
    const code = codeTemplate.replace(/\{n\}/g, String(n));
    const t = trace(code, { maxSteps: 500_000, timeoutMs: 5000 });
    if (t.error) break; // don't trust samples after a failure
    samples.push({ n, ops: t.finalOps });
    if (t.truncated) break; // stop at the first size that overflows
  }
  return samples;
}

/**
 * Classify samples into a complexity class.
 *
 * Approach: for each candidate class, compute a scaling ratio
 *   ratio(n) = ops(n) / expected(n)
 * and measure the coefficient of variation (stddev / mean). The class
 * with the lowest CV wins (flattest ratio = best fit).
 */
export function classify(samples: Sample[]): ComplexityResult {
  if (samples.length < 2) {
    return { samples, class: "unknown", confidence: 0 };
  }

  const candidates: Array<{ name: ComplexityClass; f: (n: number) => number }> = [
    { name: "O(1)", f: () => 1 },
    { name: "O(log n)", f: (n) => Math.max(1, Math.log2(n)) },
    { name: "O(n)", f: (n) => n },
    { name: "O(n log n)", f: (n) => n * Math.max(1, Math.log2(n)) },
    { name: "O(n²)", f: (n) => n * n },
    { name: "O(n³)", f: (n) => n * n * n },
    { name: "O(2^n)", f: (n) => Math.pow(2, n) },
  ];

  let best: ComplexityResult = { samples, class: "unknown", confidence: 0 };
  let bestCv = Infinity;

  for (const { name, f } of candidates) {
    const ratios = samples.map((s) => s.ops / f(s.n));
    const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;
    if (mean === 0 || !Number.isFinite(mean)) continue;
    const variance =
      ratios.reduce((a, b) => a + (b - mean) ** 2, 0) / ratios.length;
    const stddev = Math.sqrt(variance);
    const cv = stddev / mean;
    if (!Number.isFinite(cv)) continue;

    if (cv < bestCv) {
      bestCv = cv;
      // Confidence: 1 at CV=0, 0 at CV=1+
      const confidence = Math.max(0, Math.min(1, 1 - cv));
      best = { samples, class: name, confidence };
    }
  }

  return best;
}
