import os
from pathlib import Path
from .parser import parse_code



def _module_name_from_path(file_path: str, root: str) -> str:
    """Convert /project/a/b/c.py → a.b.c (relative to root)."""
    rel = os.path.relpath(file_path, root)
    return rel.replace(os.sep, ".").removesuffix(".py")


def _collect_python_files(path: str, skip_dirs: set | None = None) -> list[str]:
    """Return all .py files under path (file or directory)."""
    if os.path.isfile(path):
        return [path] if path.endswith(".py") else []
    files = []
    skip_dirs = skip_dirs or set()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(dirpath, fname))
    return sorted(files)



def _analyze_single_file(file_path: str, root: str) -> dict:
    """Parse one file and return raw parsed data + metadata."""
    module_name = _module_name_from_path(file_path, root)
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
    except OSError as e:
        return {"file": file_path, "module": module_name, "error": str(e)}

    parsed = parse_code(code, module_name=module_name)
    parsed["file"] = file_path
    parsed["module"] = module_name
    return parsed



def build_graph(path: str, skip_dirs: set | None = None) -> dict:
    """Analyse a file or directory and return a unified graph dict."""
    path = os.path.abspath(path)
    root = path if os.path.isdir(path) else os.path.dirname(path)

    files = _collect_python_files(path, skip_dirs=skip_dirs)
    if not files:
        return {"error": "No Python files found at the given path"}

    parsed_files: list[dict] = []
    for fp in files:
        parsed_files.append(_analyze_single_file(fp, root))

    module_exports: dict[str, set[str]] = {}
    for pf in parsed_files:
        mod = pf.get("module", "")
        names = set(pf.get("functions", {}).keys()) | set(pf.get("classes", {}).keys())
        module_exports[mod] = names

    nodes: list[dict] = []
    node_ids: set[str] = set()

    def add_node(node_id: str, node_type: str, **kwargs):
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({"id": node_id, "type": node_type, **kwargs})

    for pf in parsed_files:
        mod = pf.get("module", "")
        add_node(mod, "module", file=pf.get("file", ""))

        for cls_name, cls_info in pf.get("classes", {}).items():
            nid = f"{mod}::{cls_name}"
            add_node(nid, "class",
                     name=cls_name,
                     module=mod,
                     bases=cls_info["bases"],
                     lineno=cls_info["lineno"])

        for qname, fn_info in pf.get("functions", {}).items():
            nid = f"{mod}::{qname}"
            add_node(nid, "function",
                     name=fn_info["name"],
                     qualified_name=qname,
                     module=mod,
                     class_name=fn_info["class_name"],
                     lineno=fn_info["lineno"])

    edges: list[dict] = []
    known_node_ids: set[str] = {n["id"] for n in nodes}

    def add_edge(src: str, dst: str, edge_type: str, **kwargs):
        if src not in known_node_ids or dst not in known_node_ids:
            return
        edges.append({"from": src, "to": dst, "type": edge_type, **kwargs})

    for pf in parsed_files:
        mod = pf.get("module", "")

        for cls_name in pf.get("classes", {}):
            add_edge(mod, f"{mod}::{cls_name}", "contains")

        for cls_name, cls_info in pf.get("classes", {}).items():
            for method_qname in cls_info["methods"]:
                add_edge(f"{mod}::{cls_name}", f"{mod}::{method_qname}", "contains")

        for cls_name, cls_info in pf.get("classes", {}).items():
            for base in cls_info["bases"]:
                resolved = _resolve_name(base, mod, module_exports)
                add_edge(f"{mod}::{cls_name}", resolved, "inherits")

        for qname, fn_info in pf.get("functions", {}).items():
            if fn_info["class_name"] is None:
                add_edge(mod, f"{mod}::{qname}", "contains")

        for qname, fn_info in pf.get("functions", {}).items():
            caller_id = f"{mod}::{qname}"
            for call in fn_info["calls"]:
                resolved = _resolve_name(call, mod, module_exports)
                add_edge(caller_id, resolved, "calls")

        for imp in pf.get("imports", []):
            target_mod = imp["module"]
            if imp["names"]:
                for name in imp["names"]:
                    target_id = _resolve_name(name, target_mod, module_exports)
                    add_edge(mod, target_id, "imports", via=target_mod, name=name)
            else:
                add_edge(mod, target_mod, "imports")

    per_file_summary = []
    for pf in parsed_files:
        if "error" in pf:
            per_file_summary.append({"module": pf.get("module"), "error": pf["error"]})
            continue
        per_file_summary.append({
            "module": pf["module"],
            "file": pf["file"],
            "classes": list(pf.get("classes", {}).keys()),
            "functions": list(pf.get("functions", {}).keys()),
            "imports": [
                f"from {i['module']} import {', '.join(i['names'])}"
                if i["is_from"] else f"import {i['module']}"
                for i in pf.get("imports", [])
            ],
        })

    return {
        "root": path,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "total_files": len(files),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "files": per_file_summary,
        },
    }



def _resolve_name(name: str, current_module: str, module_exports: dict) -> str:
    """Try to find the fully-qualified node id for a bare name or dotted name."""
    if "." in name:
        parts = name.split(".")
        for split in range(len(parts) - 1, 0, -1):
            mod = ".".join(parts[:split])
            sym = ".".join(parts[split:])
            if mod in module_exports and sym in module_exports[mod]:
                return f"{mod}::{sym}"
        return name

    if name in module_exports.get(current_module, set()):
        return f"{current_module}::{name}"

    for mod, exports in module_exports.items():
        if name in exports:
            return f"{mod}::{name}"

    return name



def analyze_file(file_path: str) -> dict:
    """Legacy single-file API — now delegates to build_graph."""
    return build_graph(file_path, skip_dirs=skip_dirs)