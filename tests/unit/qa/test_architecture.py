"""Guard cấu trúc: cấu hình chỉ ở settings, tầng dưới không import tầng trên."""

import ast
import re
from pathlib import Path

from core.settings_loader import REPO_ROOT

_BACKEND = [
    "api",
    "auth",
    "catalogs",
    "core",
    "db",
    "embedding",
    "evaluation",
    "ingestion",
    "knowledge",
    "llm",
    "query",
    "records",
    "reranking",
    "retrieval",
    "review",
    "scoring",
    "scripts",
    "ui",
    "vectorstore",
]
_ENV_ALLOWED = {"core/settings_loader.py", "core/logging_setup.py"}
# Tầng → các package nó KHÔNG được import (pipeline một chiều, core là đáy).
_FORBIDDEN = {
    "core": {
        "api",
        "embedding",
        "vectorstore",
        "reranking",
        "retrieval",
        "llm",
        "ingestion",
        "query",
        "evaluation",
        "ui",
    },
    "embedding": {"api", "vectorstore", "reranking", "retrieval", "llm", "evaluation", "ui"},
    "vectorstore": {"api", "reranking", "retrieval", "llm", "evaluation", "ui"},
    "reranking": {"api", "retrieval", "llm", "evaluation", "ui"},
    "retrieval": {"api", "llm", "evaluation", "ui"},
    "llm": {"api", "retrieval", "vectorstore", "embedding", "evaluation", "ui"},
    "scoring": {"api", "evaluation", "ui"},
}
_HARDCODED = re.compile(r"localhost:(6333|8010|8011|11434)|qwen2\.5:\d|BAAI/bge-")


def _sources():
    for pkg in _BACKEND:
        yield from (REPO_ROOT / pkg).rglob("*.py")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_only_settings_loader_reads_environment():
    offenders = []
    for path in _sources():
        if _rel(path) in _ENV_ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"os\.(getenv|environ)(?!\.copy\(\))", text):
            offenders.append(f"{_rel(path)}:{text[: match.start()].count(chr(10)) + 1}")
    assert offenders == []


def test_no_hardcoded_service_urls_or_model_names():
    offenders = [_rel(p) for p in _sources() if _HARDCODED.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def _imported_packages(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_layers_do_not_import_upward():
    violations = []
    for layer, forbidden in _FORBIDDEN.items():
        for path in (REPO_ROOT / layer).rglob("*.py"):
            bad = _imported_packages(path) & forbidden
            if bad:
                violations.append(f"{_rel(path)} -> {sorted(bad)}")
    assert violations == []


def test_root_has_no_backend_modules_left():
    leftovers = ["api_server.py", "generation.py", "latex.py", "ingestion_jobs.py", "app.py"]
    assert [name for name in leftovers if (REPO_ROOT / name).exists()] == []
