# Review: LeetCode Backend Graph

## 📦 Corpus

A distributed code execution backend similar to LeetCode, including:

* Worker-based execution system
* Container pooling
* Redis caching
* RabbitMQ queue
* Sandbox execution

---

## ✅ What Graph Got Right

* Extracts fine-grained entities:

  * functions, classes, methods
* Captures execution flow:

  * `executeCode → compile → executeAllTestCases`
* Represents system architecture:

  * Executor → Pool → Container → Sandbox
* Includes infrastructure components:

  * Redis (caching), RabbitMQ (queue)
* Produces a well-connected graph
* Call relationships are accurate and meaningful

---

## ❌ What Graph Got Wrong

* Code-to-concept linking is still shallow (mostly module-level)
* Some duplicate entities are not fully merged:

  * e.g., `getCacheKey()` across modules
* Utility functions add noise without strong semantic value
* Missing abstraction hierarchy between concepts
* Some semantic nodes are weakly connected to implementation

---

## 🔍 Observations

* Fine-grained extraction significantly improves graph usefulness
* Canonical identity helps reduce duplication
* Execution pipeline is clearly represented
* Distributed system components are well captured

---

## 💡 Suggestions

* Improve function-level semantic linking (function ↔ concept)
* Introduce embedding-based similarity for better alignment
* Add concept hierarchy (e.g., queue → messaging system)
* Filter or down-weight low-value utility nodes

---

## 🧠 Conclusion

The graph successfully represents a real-world distributed backend system with strong structural accuracy. The semantic layer is integrated with the AST graph, though deeper entity-level alignment can further improve quality.
