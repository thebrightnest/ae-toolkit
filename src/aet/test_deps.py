"""Which test files exercise which source modules, derived from the source.

`_PATH_TARGETS` was a hand-maintained prefix table, and the thing it mapped —
"tests that cover this module" — is already written down in the test files
themselves. This derives it instead.

Two references count, because the suite uses both. An ``import aet.x`` is the
ordinary one. A path literal like ``"src" / "aet" / "cli" / "orchestrator.py"``
is the other: 68 of the 161 test files load a CLI module through
``SourceFileLoader`` rather than importing it, and an import scan alone misses
every one of them.

References are followed transitively through the source graph. A test that
drives ``aet.cli.main`` exercises every module ``main`` reaches, and selecting
only the module it names would under-test the change. Hub modules therefore
select a large share of the suite, which is the honest answer for a hub.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

SRC_ROOT = "src"
PACKAGE = "aet"
TESTS_ROOT = "tests"
# Executable surfaces outside the package. They cannot participate in the
# import graph, so they are leaves: a test reaches one only by naming it.
SCRIPT_ROOTS = ("scripts",)
# Extensions that are not executable surface. A README or a stray log under
# scripts/ is not something a test could cover.
_NON_CODE_SUFFIXES = frozenset({".md", ".log", ".json", ".txt", ".pyc"})

# A path segment inside a quoted string: ``"orchestrator.py"`` on its own, or
# ``bootstrap.sh`` within ``"scripts/bootstrap.sh"``. Both shapes occur — the
# first from the path-building idiom that feeds SourceFileLoader, the second
# from subprocess calls naming a script. Segments are matched by basename
# against the known source files, so one naming none of them contributes
# nothing.
_FILE_LITERAL_RE = re.compile(r'(?<=["\'/])([A-Za-z0-9_.-]+)(?=["\'/])')


# Coverage that crosses a boundary the source cannot show. A test driving a
# shell script that invokes the installed CLI exercises the Python behind it,
# but names neither the module nor anything that imports it, so no scan of the
# text can find the edge. Each entry is a claim about what a test really
# exercises, and needs a reason.
BOUNDARY_EDGES: dict[str, tuple[str, ...]] = {
    # ADR-049 §2: the installer smoke test drives scripts/install.sh, which
    # installs and invokes the CLI whose link and bootstrap behaviour lives
    # here. Declared in the table this module replaced, for the same reason.
    "src/aet/cli/setup.py": ("tests/installer/test_installer.py",),
}


def _dotted(path: Path, src_root: Path) -> str:
    """Return the importable name of a source file under ``src_root``."""
    parts = path.relative_to(src_root).with_suffix("").parts
    name = ".".join(parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _referenced_names(text: str) -> tuple[set[str], set[str]]:
    """Return (imported dotted names, quoted file basenames) in ``text``."""
    imported: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return imported, set(_FILE_LITERAL_RE.findall(text))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
    return imported, set(_FILE_LITERAL_RE.findall(text))


class DependencyMap:
    """Source modules, the graph between them, and the tests that reach each."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        src_root = repo_root / SRC_ROOT
        package_root = src_root / PACKAGE

        self._rel: dict[str, str] = {}
        texts: dict[str, str] = {}
        for path in sorted(package_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            name = _dotted(path, src_root)
            self._rel[name] = str(path.relative_to(repo_root))
            texts[name] = path.read_text(encoding="utf-8", errors="ignore")

        # Script files are leaves in the same map: they have no import graph,
        # but the tests that exercise them name them, which is the same signal.
        for root in SCRIPT_ROOTS:
            for path in sorted((repo_root / root).rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                if path.suffix in _NON_CODE_SUFFIXES:
                    continue
                rel = str(path.relative_to(repo_root))
                self._rel[rel] = rel

        self._by_basename: dict[str, list[str]] = {}
        for name, rel in self._rel.items():
            self._by_basename.setdefault(Path(rel).name, []).append(name)

        self._edges = {
            name: self._resolve(*_referenced_names(text), text=text)
            for name, text in texts.items()
        }

        self._tests: dict[str, set[str]] = {name: set() for name in self._rel}
        self._all_tests: set[str] = set()
        for path in sorted((repo_root / TESTS_ROOT).rglob("test_*.py")):
            rel = str(path.relative_to(repo_root))
            self._all_tests.add(rel)
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name in self._resolve(*_referenced_names(text), text=text):
                self._tests[name].add(rel)
                for reached in self._reachable(name):
                    self._tests[reached].add(rel)

    def _resolve(
        self, imported: Iterable[str], literals: Iterable[str], text: str = ""
    ) -> set[str]:
        """Map raw references onto source module names, dropping what is not ours."""
        names: set[str] = set()
        for dotted in imported:
            if not (dotted == PACKAGE or dotted.startswith(PACKAGE + ".")):
                continue
            # ``from aet.plan_parser import x`` yields both the module and the
            # symbol; walk up until a real module is found.
            candidate = dotted
            while candidate and candidate not in self._rel:
                candidate = candidate.rpartition(".")[0]
            if candidate:
                names.add(candidate)
        for basename in literals:
            for candidate in self._by_basename.get(basename, ()):
                # A package module is built from path parts for SourceFileLoader
                # ("src" / "aet" / "cli" / "orchestrator.py"), so the basename is
                # all there is to match. A script is named by its path, and
                # requiring that keeps a basename quoted in an unrelated fixture
                # from claiming coverage of the real file.
                if not self._is_script(candidate) or candidate in text:
                    names.add(candidate)
        return names

    def _is_script(self, name: str) -> bool:
        """Whether ``name`` is a script leaf rather than a package module.

        Script entries are keyed by their own repo-relative path; package
        modules are keyed by their importable name.
        """
        return self._rel.get(name) == name

    @lru_cache(maxsize=None)  # noqa: B019 - lifetime is the map's own
    def _reachable(self, start: str) -> frozenset[str]:
        """Every source module reachable from ``start`` through the import graph."""
        seen: set[str] = set()
        stack = [start]
        while stack:
            for nxt in self._edges.get(stack.pop(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return frozenset(seen)

    @property
    def test_files(self) -> list[str]:
        """Repo-relative paths of every collected test file, sorted."""
        return sorted(self._all_tests)

    @property
    def modules(self) -> list[str]:
        """Repo-relative paths of every source module, sorted."""
        return sorted(self._rel.values())

    def tests_for(self, source_path: str) -> list[str]:
        """Return the test files that reach ``source_path``, sorted.

        An empty list means nothing in the suite reaches the module — the
        caller's cue to fall back to the full suite rather than run nothing.
        """
        extra = {
            path
            for path in BOUNDARY_EDGES.get(source_path, ())
            if path in self._all_tests
        }
        for name, rel in self._rel.items():
            if rel == source_path:
                return sorted(self._tests[name] | extra)
        return sorted(extra)


@lru_cache(maxsize=4)
def dependency_map(repo_root: str) -> DependencyMap:
    """Return the cached dependency map for ``repo_root``.

    Building it parses every source and test file, which costs well under a
    second; the cache keeps a single process from paying it twice.
    """
    return DependencyMap(Path(repo_root))
