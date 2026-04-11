# Graph Report - .  (2026-04-11)

## Corpus Check
- Corpus is ~17,278 words - fits in a single context window. You may not need a graph.

## Summary
- 119 nodes · 154 edges · 12 communities detected
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `ContainerPool` - 14 edges
2. `PerformanceMonitor` - 12 edges
3. `executeCode()` - 9 edges
4. `RedisPool` - 8 edges
5. `RabbitMQPool` - 6 edges
6. `compile()` - 6 edges
7. `Container Pool Architecture` - 6 edges
8. `DockerPool` - 5 edges
9. `spawnWithTimeout()` - 3 edges
10. `executeCode()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Judger 1-like Architecture Upgrade` --references--> `Container Pool Architecture`  [EXTRACTED]
  JUDGER_UPGRADE.md → CONTAINER_POOL_ARCHITECTURE.md
- `Container Pool Architecture` --references--> `executor.js Module`  [EXTRACTED]
  CONTAINER_POOL_ARCHITECTURE.md → JUDGER_UPGRADE.md
- `Container Pool Architecture` --references--> `pool.js Module`  [EXTRACTED]
  CONTAINER_POOL_ARCHITECTURE.md → JUDGER_UPGRADE.md
- `Container Pool Architecture` --references--> `monitor.js Module`  [EXTRACTED]
  CONTAINER_POOL_ARCHITECTURE.md → JUDGER_UPGRADE.md
- `executor.js Module` --conceptually_related_to--> `Sandbox Executor Module`  [INFERRED]
  JUDGER_UPGRADE.md → CONTAINER_POOL_ARCHITECTURE.md

## Hyperedges (group relationships)
- **Code Execution Pipeline** — executor_js, pool_js, rabbitmq_queue_system [INFERRED 0.80]

## Communities

### Community 0 - "App Container"
Cohesion: 0.13
Nodes (13): executeAdminCode(), handleMessage(), processSubmission(), updateSubmissionResult(), Container Pool Architecture, Direct In-Process Execution Engine, executor.js Module, Judger 1-like Architecture Upgrade (+5 more)

### Community 1 - "Generic Pooling"
Cohesion: 0.14
Nodes (4): closePools(), DockerPool, initializePools(), RabbitMQPool

### Community 2 - "Container Pool Mgmt"
Cohesion: 0.2
Nodes (3): ContainerPool, initializePool(), shutdownPool()

### Community 3 - "Sandbox Executor"
Cohesion: 0.25
Nodes (10): cacheBinary(), executeCode(), executeExpectedCode(), executeInContainer(), extractFirstError(), getCachedBinary(), getCacheKey(), getContainerMemoryUsage() (+2 more)

### Community 4 - "Performance Monitor"
Cohesion: 0.18
Nodes (1): PerformanceMonitor

### Community 5 - "Code Execution"
Cohesion: 0.31
Nodes (8): cacheBinary(), compile(), executeAllTestCases(), executeCode(), executeTestCase(), getCachedBinary(), getCacheKey(), spawnWithTimeout()

### Community 6 - "Redis Pool"
Cohesion: 0.39
Nodes (1): RedisPool

### Community 7 - "Utilities"
Cohesion: 0.29
Nodes (0): 

### Community 8 - "Code Compiler"
Cohesion: 0.67
Nodes (2): compile(), run()

### Community 9 - "Message Queue"
Cohesion: 0.67
Nodes (0): 

### Community 10 - "Node Integration"
Cohesion: 0.67
Nodes (0): 

### Community 11 - "Core Router"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **4 isolated node(s):** `Direct In-Process Execution Engine`, `Sandbox Executor Module`, `RabbitMQ Queue System`, `Redis Cache System`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Core Router`** (1 nodes): `core.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RedisPool` connect `Redis Pool` to `Generic Pooling`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **What connects `Direct In-Process Execution Engine`, `Sandbox Executor Module`, `RabbitMQ Queue System` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `App Container` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._
- **Should `Generic Pooling` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._