"""The architecture rule as a test: layers don't call each other sideways.
Only the orchestrator (and the API, which hands requests to it) may import the layers."""
import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
LAYERS = ["ingestion", "knowledge", "llm", "actions"]


def imported_layers(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            first = node.module.split(".")[0]
            if node.level >= 2 and first in LAYERS + ["orchestrator", "api"]:
                found.add(first)
    return found


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_does_not_import_other_layers(layer):
    for path in (APP / layer).glob("*.py"):
        assert imported_layers(path) == set(), f"{path.name} reaches into {imported_layers(path)}"
