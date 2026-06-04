import ast
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionInfo:
    name: str
    qualified_name: str          # e.g. MyClass::my_method
    class_name: Optional[str]    # None if module-level
    calls: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class ClassInfo:
    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class ImportInfo:
    module: str                  # e.g. "os.path", "analyzer.parser"
    names: list[str]             # specific names imported; empty = whole module
    alias: Optional[str] = None  # import x as y  →  alias = "y"
    is_from: bool = False        # from x import y


class CodeParser(ast.NodeVisitor):
    def __init__(self, module_name: str = ""):
        self.module_name = module_name
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.imports: list[ImportInfo] = []

        self._class_stack: list[str] = []
        self._func_stack: list[str] = []


    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(ImportInfo(
                module=alias.name,
                names=[],
                alias=alias.asname,
                is_from=False,
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        names = [alias.name for alias in node.names]
        self.imports.append(ImportInfo(
            module=module,
            names=names,
            alias=None,
            is_from=True,
        ))


    def visit_ClassDef(self, node: ast.ClassDef):
        name = node.name
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(self._attr_chain(base))

        self.classes[name] = ClassInfo(
            name=name,
            bases=bases,
            lineno=node.lineno,
        )

        self._class_stack.append(name)
        self.generic_visit(node)
        self._class_stack.pop()


    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_func(node)

    def _handle_func(self, node):
        func_name = node.name
        class_name = self._class_stack[-1] if self._class_stack else None
        qualified = f"{class_name}::{func_name}" if class_name else func_name

        info = FunctionInfo(
            name=func_name,
            qualified_name=qualified,
            class_name=class_name,
            lineno=node.lineno,
        )
        self.functions[qualified] = info

        if class_name and qualified not in self.classes[class_name].methods:
            self.classes[class_name].methods.append(qualified)

        self._func_stack.append(qualified)
        self.generic_visit(node)
        self._func_stack.pop()


    def visit_Call(self, node: ast.Call):
        if self._func_stack:
            caller = self._func_stack[-1]
            callee = self._resolve_call(node.func)
            if callee:
                self.functions[caller].calls.append(callee)
        self.generic_visit(node)

    def _resolve_call(self, func_node) -> Optional[str]:
        """Resolve what is being called."""
        if isinstance(func_node, ast.Name):
            return func_node.id

        if isinstance(func_node, ast.Attribute):
            chain = self._attr_chain(func_node)
            # Normalise self.foo → just foo (relative within same class)
            if chain.startswith("self."):
                return chain[5:]
            return chain

        return None

    def _attr_chain(self, node: ast.Attribute) -> str:
        """Reconstruct dotted name from nested Attribute nodes."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))



def parse_code(code: str, module_name: str = "") -> dict:
    """Parse Python source and return structured info."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"error": str(e), "functions": {}, "classes": {}, "imports": []}

    parser = CodeParser(module_name=module_name)
    parser.visit(tree)

    return {
        "functions": {
            qname: {
                "name": info.name,
                "qualified_name": info.qualified_name,
                "class_name": info.class_name,
                "calls": info.calls,
                "lineno": info.lineno,
            }
            for qname, info in parser.functions.items()
        },
        "classes": {
            name: {
                "name": info.name,
                "bases": info.bases,
                "methods": info.methods,
                "lineno": info.lineno,
            }
            for name, info in parser.classes.items()
        },
        "imports": [
            {
                "module": imp.module,
                "names": imp.names,
                "alias": imp.alias,
                "is_from": imp.is_from,
            }
            for imp in parser.imports
        ],
    }