"""Tests for `aet hooks install` / `aet hooks check` (aet-setup/bin/hooks).

The generated pre-push shim is exercised as a real artifact: tests install it
into a temp git repo and execute it as a subprocess, and `hooks check` is
driven through its stdin-driven CLI surface with a controlled evidence home.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evidence

_REPO_ROOT = Path(__file__).parent.parent
_HOOKS_BIN = _REPO_ROOT / "aet-setup" / "bin" / "hooks"
_AET_PY = _REPO_ROOT / "aet-work" / "bin" / "aet"

_hooks_spec = importlib.util.spec_from_loader(
    "aet_hooks", importlib.machinery.SourceFileLoader("aet_hooks", str(_HOOKS_BIN))
)
hooks = importlib.util.module_from_spec(_hooks_spec)
_hooks_spec.loader.exec_module(hooks)

_aet_spec = importlib.util.spec_from_loader(
    "aet_dispatcher", importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_PY))
)
aet = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet)

ZERO = "0" * 40
SHA = "1" * 40
SLUG = "test/project"


def _init_git_repo(repo_root: str) -> None:
    """Initialize a minimal git repo with a committed main branch."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"], check=True
    )
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)


def _run_hooks(argv, stdin_text=None, env=None):
    """Invoke the hooks CLI, capturing stdout/stderr. Returns (rc, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    stdin = io.StringIO(stdin_text) if stdin_text is not None else sys.stdin
    with patch.dict(os.environ, env or {}, clear=False):
        with patch("sys.stdin", stdin):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = hooks.main(argv)
    return rc, out.getvalue(), err.getvalue()


def _hooks_dir(repo_root: str) -> Path:
    out = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--git-path", "hooks"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    path = Path(out)
    if not path.is_absolute():
        path = Path(repo_root) / path
    return path


def _write_plan(repo_root: str, task_id: str, extra: str = "") -> Path:
    plan = Path(repo_root, "docs", "plans", f"{task_id}.md")
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        f"---\nid: {task_id}\nsize: S\n{extra}---\n\n# {task_id}\n\n_Stage: implemented_\n",
        encoding="utf-8",
    )
    return plan


def _write_verdict(reports_root: str, task_id: str, kind: str, verdict: str) -> Path:
    path = evidence.evidence_path(
        task_id=task_id, kind=kind, project_slug=SLUG, reports_root=reports_root
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"verdict": verdict}) + "\n", encoding="utf-8")
    return path


def _ref(branch: str, local_sha: str = SHA) -> str:
    return f"refs/heads/{branch} {local_sha} refs/heads/{branch} {SHA}\n"


class TestInstall(unittest.TestCase):
    def test_install_generates_self_contained_pre_push_hook(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            rc, out, err = _run_hooks(["install", "--repo", repo])
            self.assertEqual(rc, 0, err)
            hook = _hooks_dir(repo) / "pre-push"
            self.assertTrue(hook.is_file())
            self.assertFalse(hook.is_symlink(), "hook must be generated, not symlinked")
            self.assertTrue(os.access(hook, os.X_OK), "hook must be executable")
            body = hook.read_text(encoding="utf-8")
            self.assertIn(hooks.SHIM_MARKER, body)
            self.assertIn("aet hooks check", body)
            # Self-contained: the AET check never depends on a committed repo file.
            self.assertIn('if [ -x "scripts/hooks/pre-push" ]', body)

    def test_install_works_with_no_committed_scripts_hook(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            self.assertFalse(Path(repo, "scripts", "hooks", "pre-push").exists())
            rc, out, err = _run_hooks(["install", "--repo", repo])
            self.assertEqual(rc, 0, err)
            self.assertTrue((_hooks_dir(repo) / "pre-push").is_file())

    def test_install_is_idempotent_on_rerun(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            hook = _hooks_dir(repo) / "pre-push"
            rc1, _, err1 = _run_hooks(["install", "--repo", repo])
            first = hook.read_text(encoding="utf-8")
            rc2, out2, err2 = _run_hooks(["install", "--repo", repo])
            second = hook.read_text(encoding="utf-8")
            self.assertEqual(rc1, 0, err1)
            self.assertEqual(rc2, 0, err2)
            self.assertEqual(first, second, "re-run must rewrite the same shim")
            self.assertTrue(os.access(hook, os.X_OK))

    def test_install_warns_and_does_not_clobber_existing_non_aet_hook(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            hook = _hooks_dir(repo) / "pre-push"
            original = "#!/usr/bin/env bash\n# team's own hook\necho custom\n"
            hook.write_text(original, encoding="utf-8")
            rc, out, err = _run_hooks(["install", "--repo", repo])
            self.assertEqual(rc, 0)
            self.assertEqual(hook.read_text(encoding="utf-8"), original)
            self.assertIn("existing", (out + err).lower())

    def test_generated_hook_chains_to_repo_local_script_when_present(self):
        with tempfile.TemporaryDirectory() as repo:
            with tempfile.TemporaryDirectory() as stub_bin:
                _init_git_repo(repo)
                sentinel = Path(repo, "companion-ran")
                companion = Path(repo, "scripts", "hooks", "pre-push")
                companion.parent.mkdir(parents=True, exist_ok=True)
                companion.write_text(
                    "#!/usr/bin/env bash\ntouch companion-ran\n", encoding="utf-8"
                )
                companion.chmod(0o755)
                # Stub the global `aet` so the evidence check passes.
                aet_stub = Path(stub_bin, "aet")
                aet_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                aet_stub.chmod(0o755)

                rc, _, err = _run_hooks(["install", "--repo", repo])
                self.assertEqual(rc, 0, err)
                hook = _hooks_dir(repo) / "pre-push"

                env = os.environ.copy()
                env["PATH"] = f"{stub_bin}:{env['PATH']}"
                result = subprocess.run(
                    [str(hook), "origin", "https://example.com/repo.git"],
                    input=_ref("demo"),
                    capture_output=True,
                    text=True,
                    cwd=repo,
                    env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(sentinel.exists(), "companion was not chained")


class TestCheck(unittest.TestCase):
    def _env(self, reports: str) -> dict:
        return {"AET_REPORTS_DIR": reports, "AET_PROJECT_ID": SLUG}

    def test_hooks_check_refuses_task_branch_missing_required_gate(self):
        with tempfile.TemporaryDirectory() as repo:
            with tempfile.TemporaryDirectory() as reports:
                _init_git_repo(repo)
                # security_review required (default) -> cso gate is required.
                _write_plan(repo, "demo", "docs_sync: skipped\ndocs_sync_reason: none\n")
                _write_verdict(reports, "demo", "qa", "pass")
                _write_verdict(reports, "demo", "review", "pass")
                # No cso verdict recorded.
                rc, out, err = _run_hooks(
                    ["check", "--repo", repo],
                    stdin_text=_ref("demo"),
                    env=self._env(reports),
                )
                self.assertNotEqual(rc, 0)
                self.assertIn("cso", out + err)
                self.assertIn("demo", out + err)

    def test_hooks_check_allows_task_branch_with_all_gates_recorded(self):
        with tempfile.TemporaryDirectory() as repo:
            with tempfile.TemporaryDirectory() as reports:
                _init_git_repo(repo)
                _write_plan(repo, "demo")
                for kind in ("qa", "review", "cso", "sync-docs"):
                    _write_verdict(reports, "demo", kind, "pass")
                rc, out, err = _run_hooks(
                    ["check", "--repo", repo],
                    stdin_text=_ref("demo"),
                    env=self._env(reports),
                )
                self.assertEqual(rc, 0, out + err)

    def test_hooks_check_noop_on_non_task_branch(self):
        with tempfile.TemporaryDirectory() as repo:
            with tempfile.TemporaryDirectory() as reports:
                _init_git_repo(repo)
                # No plan for "random-branch"; no verdicts at all.
                rc, out, err = _run_hooks(
                    ["check", "--repo", repo],
                    stdin_text=_ref("random-branch"),
                    env=self._env(reports),
                )
                self.assertEqual(rc, 0, out + err)


class TestDispatchRouting(unittest.TestCase):
    def test_hooks_install_routed_through_aet_dispatcher(self):
        spec = aet.SUBCOMMANDS.get("hooks")
        self.assertIsNotNone(spec, "SUBCOMMANDS must gain a 'hooks' row")
        self.assertEqual(spec["target"], ("aet-setup", "hooks"))
        self.assertEqual(spec["mode"], "exec")

        captured = {}

        def mock_execvp(path, argv):
            captured["path"] = Path(path)
            captured["argv"] = argv
            raise SystemExit(0)

        with patch.object(sys, "argv", ["aet", "hooks", "install"]):
            with patch.object(aet.os, "execvp", mock_execvp):
                rc = aet.main()
        self.assertEqual(rc, 0)
        self.assertEqual(captured["path"], _REPO_ROOT / "aet-setup" / "bin" / "hooks")
        self.assertEqual(captured["argv"], ["hooks", "install"])


if __name__ == "__main__":
    unittest.main()
