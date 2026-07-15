"""AST-based detection of database-shaped calls inside loops."""

import ast
from dataclasses import asdict, dataclass


@dataclass
class Finding:
    file: str
    line: int
    pattern_type: str
    nesting_depth: int
    snippet: str


class _LoopQueryVisitor(ast.NodeVisitor):
    def __init__(self, source: str, filename: str) -> None:
        self.filename = filename
        self.lines = source.splitlines()
        self.loop_depth = 0
        self.findings: list[Finding] = []

    def visit_For(self, node: ast.For) -> None:
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self.loop_depth and self._is_db_call(node):
            self.findings.append(
                Finding(
                    file=self.filename,
                    line=node.lineno,
                    pattern_type="nested_query",
                    nesting_depth=self.loop_depth,
                    snippet=self.lines[node.lineno - 1].strip(),
                )
            )
        self.generic_visit(node)

    @staticmethod
    def _call_path(node: ast.Call) -> str:
        parts: list[str] = []
        current: ast.AST = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _is_db_call(self, node: ast.Call) -> bool:
        path = self._call_path(node)
        return path.endswith((".query.get", ".objects.get", ".cursor.execute"))


def analyze_code(source_code: str, filename: str = "<string>") -> dict:
    """Return nested database-call findings from Python source code."""
    try:
        tree = ast.parse(source_code, filename=filename)
    except SyntaxError as error:
        return {"findings": [], "error": f"Syntax error: {error}"}

    visitor = _LoopQueryVisitor(source_code, filename)
    visitor.visit(tree)
    return {"findings": [asdict(finding) for finding in visitor.findings]}
