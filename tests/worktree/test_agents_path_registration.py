"""Every file the toolkit writes under `.agents/` is declared, and declared once.

`AET_IGNORED_PATHS` says "do not track this" and feeds both the `.gitignore`
writer and the hygiene gate. `AET_TOLERATED_DIRTY_PATHS` says "track this, but
do not halt on it" and feeds the hygiene gate only. A path that appears in
neither halts an unattended run the first time the toolkit writes it (ADR-027),
so this module asserts the registration itself, not just today's entries.
"""

from __future__ import annotations

import ast
import importlib
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import worktree
from tests.cli._helpers import run_typer

aet_setup = importlib.import_module("aet.cli.setup")
learnings_cli = importlib.import_module("aet.cli.learnings")

SOURCE_ROOT = Path(worktree.__file__).resolve().parent

# Paths under `.agents/` that are meant to be tracked, committed, and to halt
# the gate when dirty: project configuration and human-authored assets, plus
# per-task evidence that ships with its own PR. Nothing here is written by the
# toolkit during an unattended run, so leaving it out of both runtime
# declarations is the deliberate answer rather than an omission.
TRACKED_AND_GATED_PATHS = {
    ".agents/aet-config.json",
    ".agents/aet-work.json",
    ".agents/doc-rules.yaml",
    ".agents/review-policy.json",
    ".agents/verify/",
    ".agents/workflows/",
}

# Every module that leaves a lock file on disk, mapped to the path that must be
# forgiven because of it. `filelock` does not unlink on release, so an
# unregistered lock halts the next run exactly as an unregistered store does.
LOCK_PATH_BY_MODULE = {
    "queue.py": ".agents/work-queue.json.lock",
    "ledger.py": ".agents/ledger.jsonl.lock",
    "learnings.py": ".agents/learnings.jsonl.lock",
    "integration_lock.py": ".agents/integration.lock",
    # Handoff notes lock beside themselves inside the per-run directory.
    "handoff.py": ".agents/runs/",
}

_AGENTS_LITERAL = re.compile(r"\.agents/[A-Za-z0-9_.{}/-]*")

# `~/.agents/skills` is the installed-skills tree, not the repository, so a
# chain rooted at the home directory is not a project path at all.
_HOME_ROOTED = re.compile(r"\bhome\b|expanduser")


def _constant_agents_paths(tree: ast.AST) -> set[str]:
    """Return `.agents/` paths spelled as string literals, minus docstrings.

    Placeholders in f-strings survive as `{...}` so the caller can truncate the
    path back to the directory the writer actually targets.
    """
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    paths: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            paths.update(_AGENTS_LITERAL.findall(node.value))
    return paths


def _joined_agents_paths(tree: ast.AST) -> set[str]:
    """Return `.agents/` paths built by joining `Path` segments with `/`.

    A writer that composes its target segment by segment is invisible to a
    literal scan, which is how a registration gets missed in the first place.
    """
    # Only the outermost node of a chain is scanned; the nested ones are
    # prefixes of it and would report the same writer several times over.
    nested = {
        id(node.left)
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
    }
    paths: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        if id(node) in nested:
            continue
        if _HOME_ROOTED.search(ast.unparse(node)):
            continue
        segments = _div_operands(node)
        if ".agents" not in segments:
            continue
        chain: list[str] = []
        for segment in segments[segments.index(".agents") :]:
            if segment is None:
                # A non-literal segment: the writer targets everything under
                # the directory resolved so far.
                chain.append("")
                break
            chain.append(segment)
        paths.add("/".join(chain))
    return paths


def _div_operands(node: ast.AST) -> list[str | None]:
    """Flatten a `/` expression into its operands, `None` for non-literals."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _div_operands(node.left) + _div_operands(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return [None]


def _normalize(path: str) -> str | None:
    """Reduce a discovered path to the concrete target it names.

    Everything from the first placeholder onwards is dropped, leaving the
    directory the writer targets. Bare `.agents` carries no target and is
    dropped entirely.
    """
    if "{" in path:
        path = path[: path.index("{")]
    path = path.rstrip("/")
    if path in ("", ".agents"):
        return None
    return path


def discover_agents_paths() -> dict[str, set[str]]:
    """Return every `.agents/` path the toolkit's source names, by module."""
    discovered: dict[str, set[str]] = {}
    for module in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        raw = _constant_agents_paths(tree) | _joined_agents_paths(tree)
        for path in raw:
            normalized = _normalize(path)
            if normalized:
                discovered.setdefault(normalized, set()).add(module.name)
    return discovered


def _init_repo(repo_root: str) -> None:
    """Initialize a git repo with one commit so hygiene has a clean baseline."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", repo_root, "config", "user.name", "Test User"], check=True)
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "init"], check=True)


class TestLedgerRegistration(unittest.TestCase):
    """The event store and its lock are machine-local: never tracked, never dirty."""

    def test_hygiene_forgives_the_untracked_ledger(self):
        """The first command that records an event must not halt the next run."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            agents_dir = Path(repo_root, ".agents")
            agents_dir.mkdir()
            (agents_dir / "ledger.jsonl").write_text('{"id": "x"}\n', encoding="utf-8")
            (agents_dir / "ledger.jsonl.lock").write_text("", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root)

            self.assertTrue(ok, f"the ledger should be forgiven, got: {msg}")

    def test_setup_gitignores_the_ledger_and_its_lock(self):
        """A project bootstrapped by `aet setup` must never start tracking them."""
        with tempfile.TemporaryDirectory() as repo_root:
            aet_setup.write_aet_gitignore_entries(repo_root)

            lines = Path(repo_root, ".gitignore").read_text(encoding="utf-8").splitlines()

            self.assertIn(".agents/ledger.jsonl", lines)
            self.assertIn(".agents/ledger.jsonl.lock", lines)


class TestLearningsRegistration(unittest.TestCase):
    """The learnings journal is tracked and committed, and still must not halt."""

    def _commit_learnings(self, repo_root: str) -> Path:
        """Track and commit a learnings journal, returning its path."""
        learnings = Path(repo_root, ".agents", "learnings.jsonl")
        learnings.parent.mkdir(parents=True, exist_ok=True)
        learnings.write_text('{"problem": "first"}\n', encoding="utf-8")
        subprocess.run(["git", "-C", repo_root, "add", "-f", str(learnings)], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "commit", "-q", "-m", "add learnings"], check=True
        )
        return learnings

    def test_hygiene_forgives_an_appended_learning(self):
        """`aet learnings append` runs on every retro; it must not halt the next run."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            learnings = self._commit_learnings(repo_root)
            with learnings.open("a", encoding="utf-8") as handle:
                handle.write('{"problem": "second"}\n')

            ok, msg = worktree.check_base_hygiene(repo_root)

            self.assertTrue(ok, f"an appended learning should be forgiven, got: {msg}")

    def test_setup_does_not_gitignore_the_learnings_journal(self):
        """Ignoring it would silently stop learnings from ever being committed."""
        with tempfile.TemporaryDirectory() as repo_root:
            aet_setup.write_aet_gitignore_entries(repo_root)

            lines = Path(repo_root, ".gitignore").read_text(encoding="utf-8").splitlines()

            self.assertNotIn(".agents/learnings.jsonl", lines)

    def test_learnings_stays_tracked_after_setup_writes_the_gitignore(self):
        """The journal must remain in the index once the ignore entries land."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            self._commit_learnings(repo_root)
            aet_setup.write_aet_gitignore_entries(repo_root)

            tracked = subprocess.run(
                ["git", "-C", repo_root, "ls-files", ".agents/learnings.jsonl"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            self.assertIn(".agents/learnings.jsonl", tracked)

    def test_appending_a_learning_leaves_a_clean_tree(self):
        """End to end: the retro's own command must not dirty the base branch."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            self._commit_learnings(repo_root)

            result = run_typer(
                learnings_cli.app,
                [
                    "--problem",
                    "p",
                    "--layer",
                    "l",
                    "--fix",
                    "f",
                    "--prevents",
                    "x",
                ],
                cwd=repo_root,
            )
            self.assertEqual(result.exit_code, 0, result.output)

            ok, msg = worktree.check_base_hygiene(repo_root)

            self.assertTrue(ok, f"`aet learnings append` should leave a clean tree: {msg}")


class TestEveryAgentsPathIsRegistered(unittest.TestCase):
    """The registration itself, not today's entries: the next store must declare."""

    def _declarations_matching(self, path: str) -> list[str]:
        """Return the names of the declarations that cover ``path``."""
        matches = []
        if worktree._is_ignored_path(path):
            matches.append("AET_IGNORED_PATHS")
        if worktree.is_tolerated_dirty_path(path):
            matches.append("AET_TOLERATED_DIRTY_PATHS")
        if worktree._matches_declaration(path, TRACKED_AND_GATED_PATHS):
            matches.append("TRACKED_AND_GATED_PATHS")
        return matches

    def test_every_written_path_is_declared_exactly_once(self):
        """An unregistered path halts the first run that writes it (ADR-027)."""
        unregistered = []
        for path, modules in sorted(discover_agents_paths().items()):
            matches = self._declarations_matching(path)
            if len(matches) != 1:
                unregistered.append(f"{path} (in {', '.join(sorted(modules))}): {matches}")

        self.assertEqual(
            [],
            unregistered,
            "each `.agents/` path the toolkit names must belong to exactly one "
            "declaration — never-tracked, tolerated-dirty, or tracked-and-gated:\n"
            + "\n".join(unregistered),
        )

    def test_the_two_runtime_declarations_are_disjoint(self):
        """A path cannot be both gitignored and meant to be tracked."""
        overlap = worktree.AET_IGNORED_PATHS & worktree.AET_TOLERATED_DIRTY_PATHS

        self.assertEqual(set(), overlap)

    def test_every_lock_leaving_module_has_its_lock_forgiven(self):
        """`filelock` never unlinks; a stray lock halts as surely as a store."""
        locking_modules = {
            module.name
            for module in SOURCE_ROOT.rglob("*.py")
            if "FileLock(" in module.read_text(encoding="utf-8")
        }

        self.assertEqual(
            set(LOCK_PATH_BY_MODULE),
            locking_modules,
            "a module started or stopped leaving a lock file; map it to the path "
            "that must be forgiven, or drop it from LOCK_PATH_BY_MODULE",
        )
        for module, lock_path in sorted(LOCK_PATH_BY_MODULE.items()):
            with self.subTest(module=module):
                self.assertTrue(
                    worktree._is_ignored_path(lock_path.rstrip("/")),
                    f"{module} leaves {lock_path}, which is not declared never-tracked",
                )


if __name__ == "__main__":
    unittest.main()
