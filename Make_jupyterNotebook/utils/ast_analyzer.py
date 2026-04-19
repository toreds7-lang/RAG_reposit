import ast
from typing import Set, Tuple


def extract_assignments_and_uses(code: str) -> Tuple[Set[str], Set[str]]:
    """Extract variable assignments and uses from Python code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set(), set()

    assigned_vars = set()
    used_vars = set()

    class VarVisitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_vars.add(target.id)
                elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                    for elt in ast.walk(target):
                        if isinstance(elt, ast.Name):
                            assigned_vars.add(elt.id)
            self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):
                used_vars.add(node.id)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            assigned_vars.add(node.name)
            self.generic_visit(node)

        def visit_ClassDef(self, node):
            assigned_vars.add(node.name)
            self.generic_visit(node)

    VarVisitor().visit(tree)
    return assigned_vars, used_vars


def analyze_code_dependencies(cells: list) -> dict:
    """Analyze dependencies between code cells."""
    code_cells = [(i, c["source"]) for i, c in enumerate(cells) if c["type"] == "code"]
    dependencies = {}

    all_assigned = {}
    for idx, code in code_cells:
        assigned, _ = extract_assignments_and_uses(code)
        all_assigned[idx] = assigned

    for idx, code in code_cells:
        assigned, uses = extract_assignments_and_uses(code)

        # Find which cells define the variables this cell uses
        defines = []
        for prev_idx in range(idx):
            if prev_idx in all_assigned:
                intersection = uses & all_assigned[prev_idx]
                if intersection:
                    defines.append({
                        "cell_index": prev_idx,
                        "variables": list(intersection)
                    })

        dependencies[idx] = {
            "assigns": list(assigned),
            "uses": list(uses),
            "depends_on": defines
        }

    return dependencies


def build_dependency_edges(code_cells_indices: list, dependencies: dict) -> list:
    """Convert dependency analysis to knowledge graph edges."""
    edges = []
    for cell_idx, dep_info in dependencies.items():
        for dep in dep_info["depends_on"]:
            edges.append({
                "source": f"code_{cell_idx}",
                "target": f"code_{dep['cell_index']}",
                "type": "USES_OUTPUT_OF",
                "variables": dep["variables"]
            })
    return edges
