# LeetCode Backend Graph Benchmark

This is a worked example evaluating Graphify on a **real-world distributed code execution backend**.

## Corpus

Repository:

* https://github.com/karthick1005/Leetcode_backend

This system includes:

* Code execution engine
* Container pooling system
* Redis-based caching
* RabbitMQ-based job queue
* Sandbox execution environment

---

## How to run

Clone the repository:

```bash
git clone https://github.com/karthick1005/Leetcode_backend
cd Leetcode_backend
```

Install Graphify:

```bash
pip install graphifyy
graphify install
```

Run:

```bash
/graphify .
```

---

## What to expect

* Fine-grained nodes (functions, classes, methods)
* Execution flow captured:

  * `executeCode → compile → executeAllTestCases`
* System architecture graph:

  * Executor → Pool → Container → Sandbox
* Integration of:

  * Redis (caching)
  * RabbitMQ (queue system)

---

## Highlights

* Captures real distributed system design
* Links execution pipeline across modules
* Produces a connected graph (no major fragmentation)
* Demonstrates code + semantic integration

---

## Output

* `graph.json` — generated knowledge graph
* `review.md` — evaluation of graph quality
