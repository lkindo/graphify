# Graphify + Windsurf MCP Server Integration Guide

**Complete guide for integrating Graphify knowledge graphs with Windsurf's Model Context Protocol (MCP) system**

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [The Challenge](#the-challenge)
- [The Solution](#the-solution)
- [Step-by-Step Installation](#step-by-step-installation)
- [Configuration](#configuration)
- [Testing & Verification](#testing--verification)
- [Troubleshooting](#troubleshooting)
- [Architecture Details](#architecture-details)
- [FAQs](#faqs)
- [Contributing](#contributing)

---

## Overview

This guide provides a complete, tested solution for integrating **Graphify knowledge graphs** with **Windsurf/Cascade MCP servers**. Graphify generates multi-modal knowledge graphs from code, documentation, and other sources. By connecting it to Windsurf via MCP, Cascade gains powerful graph traversal and analysis capabilities.

**What This Guide Covers:**
- Installing Graphify and generating knowledge graphs
- Configuring Graphify MCP servers in Windsurf
- Solving the working directory (CWD) issue that causes timeouts
- Testing and verifying the integration
- Managing multiple graph scopes (project-wide, module-specific)

**Tested Environment:**
- **OS**: Windows 11 (adaptable to macOS/Linux)
- **Python**: 3.12.9
- **Windsurf**: Latest version with MCP support
- **Graphify**: 1.27.0

**Credits:**
- **Solution by**: [@pineapple-leather](https://github.com/pineapple-leather)
- **Documentation**: @pineapple-leather

---

## Prerequisites

### 1. Python Environment

Ensure Python 3.11+ is installed and accessible in your PATH:

```bash
python --version  # Should show 3.11 or higher
```

### 2. Install Graphify

```bash
pip install graphify
```

Verify installation:

```bash
python -c "import graphify; print(graphify.__file__)"
```

### 3. Install MCP Package

Graphify's MCP server requires the `mcp` package:

```bash
pip install mcp
```

### 4. Windsurf Editor

Download and install Windsurf from [windsurf.com](https://windsurf.com/).

---

## The Challenge

### Problem Statement

When attempting to configure Graphify MCP servers in Windsurf, the servers consistently timeout during initialization (60-second timeout), even though:
- Graphify is correctly installed
- Graph files exist and are valid
- Manual MCP protocol handshake succeeds

### Root Cause

**Graphify's security restriction**: The `graphify.serve` module includes a `validate_graph_path()` function that:

1. Requires graph files to be inside a `graphify-out/` directory
2. Resolves `graphify-out/` **relative to the current working directory (CWD)**
3. Exits with an error if the base directory doesn't exist

**Windsurf's execution behavior**: Windsurf executes MCP servers from its **own installation directory**, not your workspace root.

**Result**: When Windsurf starts `python -m graphify.serve graphify-out/graph.json`, Python looks for `graphify-out/` relative to Windsurf's directory (e.g., `C:\Users\<user>\.codeium\windsurf\graphify-out\`), which doesn't exist. The server exits immediately before the MCP handshake completes, causing a timeout.

### Failed Approaches

❌ **Absolute paths**: `graphify.serve` rejects paths outside `graphify-out/`  
❌ **`cwd` parameter**: Not supported in Windsurf's MCP config  
❌ **Relative paths**: Resolved relative to Windsurf's directory, not workspace  

---

## The Solution

### Wrapper Script Approach

Create a **Python wrapper script** that:
1. Changes the working directory to your workspace root
2. Then calls `graphify.serve` with relative paths

This satisfies Graphify's security requirements while allowing Windsurf to execute from any directory.

---

## Step-by-Step Installation

### Step 1: Generate Graphify Knowledge Graphs

Navigate to your project workspace and generate graphs:

```bash
cd /path/to/your/workspace

# Generate root graph (entire repository)
graphify --out graphify-out

# Generate scope-specific graphs (optional)
graphify --scope app/core --out app/core/graphify-out
graphify --scope app/venture/my_venture --out app/venture/my_venture/graphify-out
```

This creates:
- `graphify-out/graph.json` (root graph)
- `graphify-out/graph.html` (interactive visualization)
- `graphify-out/GRAPH_REPORT.md` (analysis report)
- Additional scope-specific graphs if generated

**Note**: Graph files can be large. The root graph for a medium-sized monorepo may be 5-10 MB.

### Step 2: Copy Graphs to Central Location (Optional)

**If you have multiple scope-specific graphs**, Graphify's MCP server requires all graphs to be in a single `graphify-out/` directory. Copy scope-specific graphs with unique names:

```bash
# Example: Copy module-specific graphs to central location
cp backend/graphify-out/graph.json graphify-out/backend.json
cp frontend/graphify-out/graph.json graphify-out/frontend.json
cp services/auth/graphify-out/graph.json graphify-out/auth.json
```

**Result**:
```
workspace/
├── graphify-out/
│   ├── graph.json          # Project-wide graph
│   ├── backend.json        # Backend module graph
│   ├── frontend.json       # Frontend module graph
│   ├── auth.json           # Auth service graph
│   ├── graph.html
│   └── GRAPH_REPORT.md
```

**Note**: If you only have one graph, skip this step.

### Step 3: Create MCP Wrapper Script

**Template Wrapper Script** - Save as `scripts/mcp_graphify_wrapper.py` in your workspace:

```python
#!/usr/bin/env python3
"""
MCP wrapper for graphify.serve that changes to workspace directory first.
This ensures graphify-out/ is found relative to the correct base directory.

Author: @pineapple-leather
License: MIT
"""
import os
import sys
from pathlib import Path

# Change to workspace root
# Adjust .parent count based on script location relative to workspace root:
#   scripts/wrapper.py           -> .parent.parent (up 1 level)
#   wrapper.py (at root)         -> .parent (already at root)  
#   scripts/mcp/wrapper.py       -> .parent.parent.parent (up 2 levels)
workspace_root = Path(__file__).parent.parent.resolve()
os.chdir(workspace_root)

# Import and run graphify.serve
from graphify.serve import serve

if __name__ == "__main__":
    graph_path = sys.argv[1] if len(sys.argv) > 1 else "graphify-out/graph.json"
    serve(graph_path)
```

**Alternative: Explicit Path (if auto-detection fails)**:

```python
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Explicitly set your workspace root
workspace_root = Path("/absolute/path/to/your/workspace")
os.chdir(workspace_root)

from graphify.serve import serve

if __name__ == "__main__":
    graph_path = sys.argv[1] if len(sys.argv) > 1 else "graphify-out/graph.json"
    serve(graph_path)
```

**Platform-Specific Notes**:
- **Linux/macOS**: Make executable: `chmod +x scripts/mcp_graphify_wrapper.py`
- **Windows**: No additional steps needed

### Step 4: Configure Windsurf MCP Servers

**Location of Config File**:
- **Windows**: `C:\Users\<username>\.codeium\windsurf\mcp_config.json`
- **macOS/Linux**: `~/.codeium/windsurf/mcp_config.json`

**Edit the config file**:

```json
{
  "mcpServers": {
    "graphify-root": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/graph.json"
      ]
    },
    "graphify-core": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/core.json"
      ]
    },
    "graphify-my-venture": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/my_venture.json"
      ]
    }
  }
}
```

**Important Notes**:
- Use **absolute paths** for the wrapper script (e.g., `C:/Users/you/workspace/scripts/mcp_graphify_wrapper.py`)
- Use **forward slashes** even on Windows (or double backslashes: `C:\\Users\\...`)
- Graph paths (second argument) are **relative** and resolved by the wrapper

**Alternative: UI Configuration**:

1. Open Windsurf
2. Click **MCP icon** (🔨) in Cascade panel header
3. Click **View Raw Config** button
4. Edit `mcp_config.json` directly
5. Save

### Step 5: Refresh MCP Servers in Windsurf

**Critical Step**: After editing `mcp_config.json`, you **must** refresh:

1. Click **MCP icon** (🔨) in Cascade panel
2. Click **Refresh button** (🔄) in the MCP toolbar

Windsurf will initialize the servers. This may take 5-10 seconds for large graphs.

---

## Configuration

### Single Graph Setup (Simplest)

For a single root graph:

```json
{
  "mcpServers": {
    "graphify": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/graph.json"
      ]
    }
  }
}
```

### Multi-Graph Setup (Recommended)

For multiple module/component graphs:

```json
{
  "mcpServers": {
    "graphify-project": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/graph.json"
      ]
    },
    "graphify-backend": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/backend.json"
      ]
    },
    "graphify-frontend": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/frontend.json"
      ]
    },
    "graphify-auth": {
      "command": "python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/auth.json"
      ]
    }
  }
}
```

### Environment-Specific Python

If you need a specific Python environment (e.g., virtual environment):

```json
{
  "mcpServers": {
    "graphify": {
      "command": "/path/to/venv/bin/python",
      "args": [
        "/absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py",
        "graphify-out/graph.json"
      ]
    }
  }
}
```

---

## Testing & Verification

### Step 1: Verify Servers Are Enabled

1. Open Windsurf
2. Click **MCP icon** (🔨) in Cascade panel
3. Verify your Graphify servers appear with **green/active status**

If servers show errors or timeout:
- Check wrapper script path is absolute
- Verify Python has `graphify` and `mcp` packages installed
- Check Windsurf developer logs (see Troubleshooting)

### Step 2: Test Graph Statistics

In Cascade chat, test each server:

**Using the tool directly** (if available in UI):
```
Use graphify-root's graph_stats tool
```

**Via natural language**:
```
Query the graphify-root graph for statistics
```

**Expected output**:
```
Nodes: 5152
Edges: 17045
Communities: 183
EXTRACTED: 32%
INFERRED: 68%
AMBIGUOUS: 0%
```

### Step 3: Test God Nodes Query

```
Show me the top 5 most connected nodes in graphify-core
```

**Expected output** (example):
```
God nodes (most connected):
  1. DatabaseConnection - 72 edges
  2. APIRouter - 58 edges
  3. AuthMiddleware - 45 edges
  4. UserModel - 42 edges
  5. ConfigManager - 38 edges
```

### Step 4: Test Graph Traversal

```
Query graphify-root for "database architecture" with BFS traversal depth 2
```

**Expected output**: Nodes and edges related to database architecture.

### Step 5: Test All Available Tools

Graphify MCP servers provide 7 tools:

1. **`graph_stats`** - Node/edge counts, communities, confidence breakdown
2. **`god_nodes`** - Most connected nodes (central abstractions)
3. **`query_graph`** - BFS/DFS traversal for keyword search
4. **`get_node`** - Details for a specific node by label
5. **`get_neighbors`** - All neighbors of a node with edge details
6. **`get_community`** - All nodes in a community by ID
7. **`shortest_path`** - Shortest path between two concepts

Test each to verify full functionality.

---

## Troubleshooting

### Issue: "Server name graphify not found"

**Symptoms**: MCP server doesn't appear in Windsurf UI or tool calls fail with "server name not found".

**Solutions**:
1. **Verify config location**: Ensure you edited `~/.codeium/windsurf/mcp_config.json` (global), not a workspace-specific file
2. **Click Refresh**: After editing config, **must** click Refresh (🔄) in MCP UI
3. **Restart Windsurf**: Sometimes required after first-time configuration
4. **Check JSON syntax**: Use `python -m json.tool mcp_config.json` to validate

### Issue: "MCP initialization timeout"

**Symptoms**: Server shows loading spinner for 60 seconds, then times out.

**Diagnosis**:
1. **Test wrapper manually**:
   ```bash
   cd /tmp  # Different directory to simulate Windsurf's behavior
   python /absolute/path/to/workspace/scripts/mcp_graphify_wrapper.py graphify-out/graph.json
   ```
   Should start without errors.

2. **Test MCP handshake**:
   ```bash
   echo '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": 1}' | python /absolute/path/to/wrapper.py graphify-out/graph.json
   ```
   Should return JSON response with `"result"` and server info.

**Common Causes**:
- **Wrapper path wrong**: Must be absolute path, not relative
- **Python environment**: Wrapper uses wrong Python (missing `graphify` or `mcp`)
- **Graph file missing**: Wrapper changes to workspace, but `graphify-out/graph.json` doesn't exist
- **Permissions**: Wrapper script not executable (Linux/macOS: `chmod +x wrapper.py`)

**Solutions**:
1. Use **absolute path** for wrapper script in `mcp_config.json`
2. Verify `graphify` and `mcp` packages in Python:
   ```bash
   python -c "import graphify, mcp; print('OK')"
   ```
3. Verify graph files exist:
   ```bash
   ls workspace/graphify-out/*.json
   ```

### Issue: "Graph base directory does not exist"

**Symptoms**: Wrapper runs but exits with error about `graphify-out/` not existing.

**Cause**: Wrapper's `Path(__file__).parent.parent` doesn't resolve to workspace root.

**Solutions**:
1. **Check wrapper location**: If script is at `scripts/mcp/wrapper.py`, need `.parent.parent.parent` (3 levels up)
2. **Verify workspace structure**:
   ```python
   # Add debug to wrapper.py
   print(f"Workspace root: {workspace_root}")
   print(f"graphify-out exists: {(workspace_root / 'graphify-out').exists()}")
   ```
3. **Use explicit path** in wrapper:
   ```python
   workspace_root = Path("/absolute/path/to/workspace")
   ```

### Issue: Large graphs are slow to load

**Symptoms**: Server takes 15-30 seconds to initialize.

**Explanation**: This is normal for large graphs (>5000 nodes). Windsurf's 60-second timeout should accommodate this.

**Optimizations**:
1. **Split into smaller graphs**: Create scope-specific graphs instead of one massive root graph
2. **Increase graph quality threshold**: Use `graphify --confidence-threshold 0.8` to filter low-confidence edges
3. **Filter file types**: Use `.graphifyignore` to exclude unnecessary files

### Issue: Server works in CLI but not in Windsurf

**Symptoms**: Manual MCP handshake succeeds, but Windsurf reports timeout.

**Diagnosis**:
1. **Check Python executable**:
   ```bash
   which python  # Linux/macOS
   where python  # Windows
   ```
   Ensure Windsurf uses the same Python.

2. **Specify full Python path** in `mcp_config.json`:
   ```json
   {
     "mcpServers": {
       "graphify": {
         "command": "/usr/local/bin/python3",
         "args": ["..."]
       }
     }
   }
   ```

3. **Check Windsurf logs** (if available):
   - **macOS/Linux**: `~/.codeium/windsurf/logs/`
   - **Windows**: `C:\Users\<user>\.codeium\windsurf\logs\`

### Issue: "Tool count exceeds 100 limit"

**Symptoms**: Windsurf warns about too many MCP tools.

**Cause**: Windsurf limits total MCP tools to 100. Each Graphify server adds 7 tools.

**Solution**: Limit to **14 or fewer MCP servers** total (including non-Graphify servers). Consolidate graphs if needed.

---

## Architecture Details

### How Graphify MCP Servers Work

```
Windsurf
  ↓ starts
Python subprocess: mcp_graphify_wrapper.py
  ↓ changes CWD to workspace
graphify.serve module
  ↓ loads
graphify-out/graph.json (via validate_graph_path)
  ↓ builds NetworkX graph
MCP Server (stdio transport)
  ↓ exposes 7 tools
Cascade uses tools via MCP protocol
```

### MCP Protocol Flow

1. **Initialization**: Windsurf sends `initialize` request with protocol version
2. **Handshake**: Server responds with capabilities (tools, prompts, resources)
3. **Tool Discovery**: Windsurf queries available tools
4. **Tool Execution**: Cascade calls tools (e.g., `graph_stats`), server returns results
5. **Streaming**: Server uses stdio (stdin/stdout) for JSON-RPC messages

### Graphify Server Tools

| Tool | Description | Inputs | Use Case |
|------|-------------|--------|----------|
| `graph_stats` | Node/edge counts, communities | None | Overview of graph size and structure |
| `god_nodes` | Most connected nodes | `top_n` (int) | Find central abstractions/concepts |
| `query_graph` | BFS/DFS traversal | `question`, `mode`, `depth`, `token_budget` | Semantic search for concepts |
| `get_node` | Node details | `label` (string) | Look up specific class/function |
| `get_neighbors` | Node neighbors | `label`, `relation_filter` | Explore dependencies/relationships |
| `get_community` | Community nodes | `community_id` (int) | Find related modules/concepts |
| `shortest_path` | Path between nodes | `source`, `target`, `max_hops` | Trace dependencies/influence |

### Directory Structure

**Recommended workspace layout**:

```
workspace/
├── scripts/
│   └── mcp_graphify_wrapper.py   # Wrapper script
├── graphify-out/                  # Central graph directory
│   ├── graph.json                 # Project-wide graph
│   ├── backend.json               # Backend module graph (optional)
│   ├── frontend.json              # Frontend module graph (optional)
│   ├── graph.html                 # Visualization
│   └── GRAPH_REPORT.md            # Analysis
├── backend/
│   └── graphify-out/              # Original backend graph (if generated separately)
│       └── graph.json
├── frontend/
│   └── graphify-out/              # Original frontend graph (if generated separately)
│       └── graph.json
└── .graphifyignore                # Exclusions
```

---

## FAQs

### Q: Do I need to rebuild graphs when code changes?

**A**: Yes, but Graphify supports **incremental updates**:

```bash
graphify --update  # Only re-extracts changed files
```

After updating, restart MCP servers (click Refresh in Windsurf MCP UI).

### Q: Can I use a different graph storage format?

**A**: Graphify MCP server requires `graph.json` (NetworkX node-link format). Other formats (GraphML, Neo4j, Obsidian) are not supported for MCP.

### Q: How do I exclude files from graphs?

Create `.graphifyignore` in workspace root:

```
# Exclude patterns
node_modules/
*.pyc
.git/
tests/
__pycache__/
```

Then regenerate graphs.

### Q: Can I run multiple Graphify MCP servers for different projects?

**A**: Yes, but each needs a unique name and wrapper script pointing to that project's workspace:

```json
{
  "mcpServers": {
    "graphify-project1": {
      "command": "python",
      "args": ["/path/to/project1/scripts/wrapper.py", "graphify-out/graph.json"]
    },
    "graphify-project2": {
      "command": "python",
      "args": ["/path/to/project2/scripts/wrapper.py", "graphify-out/graph.json"]
    }
  }
}
```

### Q: Does this work on macOS/Linux?

**A**: Yes. Adjust paths:
- Config: `~/.codeium/windsurf/mcp_config.json`
- Wrapper shebang: `#!/usr/bin/env python3`
- Make executable: `chmod +x scripts/mcp_graphify_wrapper.py`

### Q: Can Graphify integrate with graph databases like Neo4j?

**A**: Yes, Graphify can export to Neo4j, GraphML, and other formats:

```bash
graphify --export neo4j  # Export to Neo4j import format
graphify --export graphml  # Export to GraphML
```

However, these exports are separate from MCP. MCP servers use the `graph.json` format only.

### Q: Can I disable specific tools from a Graphify server?

**A**: Yes, Windsurf allows per-MCP tool toggling:

1. Click **MCP icon** (🔨)
2. Click on a Graphify server
3. Toggle individual tools on/off

This is useful if you hit the 100-tool limit.

---

## Contributing

### Reporting Issues

If you encounter issues with this integration:

1. **Graphify issues**: Report to [Graphify GitHub](https://github.com/graphify-ai/graphify)
2. **Windsurf MCP issues**: Report to Windsurf support or community
3. **This guide issues**: Open an issue on this repository

### Improvements

Contributions to this guide are welcome:
- Clarifications for confusing steps
- Additional troubleshooting scenarios
- Platform-specific instructions (Linux, macOS)
- Screenshots/videos for visual learners

---

## Changelog

### 2026-04-09 - Initial Release
- Complete integration guide created
- Tested on Windows 11, Python 3.12, Windsurf latest, Graphify 1.27.0
- Wrapper script solution documented
- 5 MCP servers successfully configured and verified

---

## Credits

**Solution By**: [@pineapple-leather](https://github.com/pineapple-leather)  
**Documentation**: @pineapple-leather 
**Tested By**: Windsurf + Graphify integration community  
**Special Thanks**: Graphify maintainers for the MCP server implementation

---

## License

This guide is released under MIT License. Feel free to share, adapt, and distribute.

---

## Quick Reference Card

**Installation Checklist**:
- [ ] Python 3.11+ installed
- [ ] `pip install graphify mcp`
- [ ] Generate graphs: `graphify --out graphify-out`
- [ ] Copy graphs to central location
- [ ] Create `scripts/mcp_graphify_wrapper.py`
- [ ] Edit `~/.codeium/windsurf/mcp_config.json`
- [ ] Click Refresh in Windsurf MCP UI
- [ ] Test with `graph_stats` query

**Common Paths**:
- **Config**: `~/.codeium/windsurf/mcp_config.json` (macOS/Linux), `C:\Users\<user>\.codeium\windsurf\mcp_config.json` (Windows)
- **Wrapper**: `workspace/scripts/mcp_graphify_wrapper.py`
- **Graphs**: `workspace/graphify-out/*.json`

**Debugging Commands**:
```bash
# Verify Python packages
python -c "import graphify, mcp; print('OK')"

# Test wrapper manually
python /path/to/wrapper.py graphify-out/graph.json

# Test MCP handshake
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | python /path/to/wrapper.py graphify-out/graph.json

# Validate JSON config
python -m json.tool ~/.codeium/windsurf/mcp_config.json
```

---

**End of Guide**
