"""
server.py  —  Code Analyzer MCP Server
Exposes 2 tools: get_graph and get_summary.

Run:
    python server.py

Windsurf config:
    "code-analyzer-mcp": { "url": "http://127.0.0.1:3000/sse" }
"""

import os
import json
import asyncio
import uvicorn
from functools import partial
from mcp.server.fastmcp import FastMCP
from analyzer.extractor import build_graph

SKIP_DIRS = {
    "venv", ".venv", "env", ".env", "__pycache__", ".git",
    "node_modules", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", "migrations", "htmlcov", ".ruff_cache",
}
MAX_NODES = 200
MAX_EDGES = 400

mcp = FastMCP("code-analyzer-mcp")


async def _analyze(path: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, partial(build_graph, path, skip_dirs=SKIP_DIRS)
    )


@mcp.tool()
async def get_graph(path: str, node_type: str = "all", edge_type: str = "all") -> str:
    """
    Return the architecture graph of a Python project.
    Nodes: modules, classes, functions.
    Edges: calls, inherits, imports (contains excluded by default).

    Args:
        path: Absolute path to a .py file or directory.
        node_type: all | module | class | function
        edge_type: all | calls | inherits | imports | contains
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return f"Path not found: {path}"

    try:
        result = await _analyze(path)
    except Exception as e:
        import traceback
        return f"Error:\n{traceback.format_exc()}"

    nodes = result["nodes"]
    edges = result["edges"]

    if node_type != "all":
        nodes = [n for n in nodes if n["type"] == node_type]

    if edge_type == "all":
        edges = [e for e in edges if e["type"] != "contains"]
    else:
        edges = [e for e in edges if e["type"] == edge_type]

    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]

    truncated = len(nodes) > MAX_NODES or len(edges) > MAX_EDGES
    nodes = nodes[:MAX_NODES]
    edges = edges[:MAX_EDGES]

    out = {
        "root": result["root"],
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "total_files": result["meta"]["total_files"],
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "truncated": truncated,
        }
    }

    note = ""
    if truncated:
        note = "\n\n⚠ Result truncated. Analyze a subdirectory or use node_type/edge_type filters for more detail."

    return json.dumps(out) + note


@mcp.tool()
async def get_summary(path: str) -> str:
    """
    Fast, readable summary of a Python project.
    Shows classes, functions, and imports per file.
    Use this before get_graph for a quick overview.

    Args:
        path: Absolute path to a .py file or directory.
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return f"Path not found: {path}"

    try:
        result = await _analyze(path)
    except Exception as e:
        import traceback
        return f"Error:\n{traceback.format_exc()}"

    lines = [f"Project: {result['root']}", ""]
    for f in result["meta"]["files"]:
        if "error" in f:
            lines.append(f"  [{f.get('module')}] ERROR: {f['error']}")
            continue
        lines.append(f"  {f['module']}")
        if f.get("classes"):
            lines.append(f"    classes:   {', '.join(f['classes'])}")
        if f.get("functions"):
            fns = f["functions"]
            preview = ", ".join(fns[:8])
            more = f" (+{len(fns)-8} more)" if len(fns) > 8 else ""
            lines.append(f"    functions: {preview}{more}")
        if f.get("imports"):
            lines.append(f"    imports:   {', '.join(f['imports'][:4])}")
        lines.append("")

    lines.append(
        f"Total: {result['meta']['total_files']} files · "
        f"{result['meta']['total_nodes']} nodes · "
        f"{result['meta']['total_edges']} edges"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    uvicorn.run(mcp.sse_app(), host="127.0.0.1", port=3000)