#!/usr/bin/env python3
"""Static audit measurements. Reads source text only; emits JSON to stdout.

No product imports, databases, network calls, or workspace initialization.
Import cycles include lazy/type-only imports and are NOT runtime-cycle proofs.
SQL counts are AST execute-family callsites; table mentions are literal SQL
tokens, not a complete dataflow analysis (dynamic SQL is deliberately omitted).
"""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]


def components(graph):
    index, stack, active, indices, low, result = 0, [], set(), {}, {}, []
    def visit(node):
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        active.add(node)
        for child in sorted(graph[node]):
            if child not in indices:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in active:
                low[node] = min(low[node], indices[child])
        if low[node] == indices[node]:
            group = []
            while True:
                child = stack.pop()
                active.remove(child)
                group.append(child)
                if child == node:
                    break
            if len(group) > 1:
                result.append(sorted(group))
    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(result)


def measure():
    files = sorted((ROOT / "hermeneia").rglob("*.py"))
    modules = {}
    trees, sources, hashes = {}, {}, {}
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        module = rel[:-3].replace("/", ".").removesuffix(".__init__")
        modules[module] = rel
        sources[rel] = text
        trees[rel] = ast.parse(text)
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    graph = {module: set() for module in modules}
    sql, routes, functions, table_consumers = {}, {}, [], defaultdict(set)
    for module, rel in modules.items():
        tree = trees[rel]
        package = module if rel.endswith("/__init__.py") else module.rsplit(".", 1)[0]
        calls = Counter()
        route_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({"file": rel, "name": node.name, "line": node.lineno,
                                  "physical_lines": node.end_lineno - node.lineno + 1})
                route_count += sum(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                                   and d.func.attr == "route" for d in node.decorator_list)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"execute", "executemany", "executescript"}:
                    calls[node.func.attr] += 1
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for table in re.findall(r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE(?: IF NOT EXISTS)?)\s+["`]?([a-z_]\w*)', node.value, re.I):
                    table_consumers[table.lower()].add(rel)
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    prefix = package.split(".")[:len(package.split(".")) - node.level + 1]
                    base = ".".join(prefix + ([node.module] if node.module else []))
                else:
                    base = node.module or ""
                imported = [base, *(base + "." + alias.name for alias in node.names)]
            for target in imported:
                if target in modules and target != module:
                    graph[module].add(target)
        if calls:
            sql[rel] = dict(sorted(calls.items()))
        if route_count:
            routes[rel] = route_count
    html_path = ROOT / "hermeneia/web/static/index.html"
    html = html_path.read_text(encoding="utf-8")
    function_names = re.findall(r"^(?:async )?function (\w+)\(", html, re.M)
    hashes[html_path.relative_to(ROOT).as_posix()] = hashlib.sha256(html_path.read_bytes()).hexdigest()
    tests = sorted((ROOT / "tests").glob("test_*.py"))
    test_texts = [p.read_text(encoding="utf-8") for p in tests]
    important_tables = ["reader_highlights", "observations", "provenance", "ai_provenance",
                        "proposed_interpretations", "interpretations", "narrative_blueprints",
                        "supersession_relations", "perspectives", "workspace_identity"]
    return {
        "method": __doc__,
        "source_set_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "python_modules": len(files),
        "largest_python_files": sorted(({"file": p, "physical_lines": len(s.splitlines())} for p, s in sources.items()), key=lambda v: (-v["physical_lines"], v["file"]))[:12],
        "largest_python_functions_including_enclosing_factories": sorted(functions, key=lambda v: (-v["physical_lines"], v["file"], v["line"]))[:15],
        "route_decorators": routes,
        "sql_callsite_modules": sql,
        "literal_sql_table_consumers": {t: sorted(table_consumers[t]) for t in important_tables},
        "lexical_internal_import_cycles": components(graph),
        "html": {"physical_lines": len(html.splitlines()),
                 "column_zero_named_functions": len(function_names),
                 "named_function_prefix_counts": {
                     prefix: sum(name.startswith(prefix) for name in function_names)
                     for prefix in ("_cr", "_cmp", "cmp", "_studyLineage", "_evidenceBoard", "e10")
                 },
                 "column_zero_const_let_declarations": len(re.findall(r"^(?:const|let) ", html, re.M)),
                 "quoted_inline_event_attribute_tokens": len(re.findall(r'''\bon[a-z]+\s*=\s*["']''', html))},
        "tests": {"root_test_files": len(tests),
                  "files_mentioning_index_html": sum("index.html" in s for s in test_texts),
                  "files_with_node_and_subprocess_run": sum("node" in s and "subprocess.run" in s for s in test_texts),
                  "files_defining_js_extractor": sum(bool(re.search(r"def _extract_(?:fn|function)\(", s)) for s in test_texts)},
    }


if __name__ == "__main__":
    print(json.dumps(measure(), sort_keys=True, indent=2))
