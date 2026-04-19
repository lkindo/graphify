/**
 * Preset algorithms to showcase the visualizer.
 * Each preset includes source code + an n-sweep template for complexity analysis.
 */

export type Preset = {
  name: string;
  description: string;
  complexity: string;
  /** Code shown in the editor and stepped through. */
  code: string;
  /** Template for n-sweep complexity measurement. `{n}` is replaced with each size. */
  complexityTemplate: string;
};

export const PRESETS: Preset[] = [
  {
    name: "Bubble Sort",
    description: "Repeatedly swap adjacent elements until the array is sorted.",
    complexity: "O(n²)",
    code: `function bubbleSort(arr) {
  for (let i = 0; i < arr.length; i++) {
    for (let j = 0; j < arr.length - i - 1; j++) {
      if (arr[j] > arr[j + 1]) {
        const tmp = arr[j];
        arr[j] = arr[j + 1];
        arr[j + 1] = tmp;
      }
    }
  }
  return arr;
}

const nums = [5, 2, 8, 1, 9, 3];
bubbleSort(nums);
console.log("sorted:", nums);`,
    complexityTemplate: `function bubbleSort(arr) {
  for (let i = 0; i < arr.length; i++) {
    for (let j = 0; j < arr.length - i - 1; j++) {
      if (arr[j] > arr[j + 1]) {
        const t = arr[j]; arr[j] = arr[j + 1]; arr[j + 1] = t;
      }
    }
  }
}
const nums = Array.from({length: {n}}, (_, i) => {n} - i);
bubbleSort(nums);`,
  },
  {
    name: "Binary Search",
    description: "Find a target value in a sorted array by halving the search space.",
    complexity: "O(log n)",
    code: `function binarySearch(arr, target) {
  let lo = 0;
  let hi = arr.length - 1;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (arr[mid] === target) return mid;
    if (arr[mid] < target) {
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return -1;
}

const sorted = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19];
const idx = binarySearch(sorted, 13);
console.log("found at index:", idx);`,
    complexityTemplate: `function binarySearch(arr, target) {
  let lo = 0, hi = arr.length - 1;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (arr[mid] === target) return mid;
    if (arr[mid] < target) lo = mid + 1; else hi = mid - 1;
  }
  return -1;
}
const arr = Array.from({length: {n}}, (_, i) => i * 2);
binarySearch(arr, -1);`,
  },
  {
    name: "Fibonacci (recursive)",
    description: "Recursive Fibonacci — the classic exponential-time example.",
    complexity: "O(2^n)",
    code: `function fib(n) {
  if (n < 2) return n;
  return fib(n - 1) + fib(n - 2);
}

const result = fib(6);
console.log("fib(6) =", result);`,
    complexityTemplate: `function fib(n) {
  if (n < 2) return n;
  return fib(n - 1) + fib(n - 2);
}
fib({n});`,
  },
  {
    name: "Linear Sum",
    description: "Sum an array — the baseline O(n) algorithm.",
    complexity: "O(n)",
    code: `function sum(arr) {
  let total = 0;
  for (let i = 0; i < arr.length; i++) {
    total += arr[i];
  }
  return total;
}

const nums = [3, 7, 2, 9, 4];
const s = sum(nums);
console.log("sum =", s);`,
    complexityTemplate: `function sum(arr) {
  let total = 0;
  for (let i = 0; i < arr.length; i++) total += arr[i];
  return total;
}
const nums = Array.from({length: {n}}, (_, i) => i);
sum(nums);`,
  },
];
