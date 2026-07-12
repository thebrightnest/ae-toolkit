"""Tests for scripts/skills-lint — documented `aet` invocations parse against the real tree."""

import contextlib
import importlib.machinery
import importlib.util
import io
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_LINT_PY = _REPO_ROOT / "scripts" / "skills-lint"
_FIXTURES = Path(__file__).parent / "fixtures" / "skills-lint"

_lint_spec = importlib.util.spec_from_loader(
    "skills_lint",
    importlib.machinery.SourceFileLoader("skills_lint", str(_LINT_PY)),
)
lint = importlib.util.module_from_spec(_lint_spec)
sys.modules["skills_lint"] = lint
_lint_spec.loader.exec_module(lint)


def run_lint(*args):
    """Run skills-lint main(); return (exit_code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = lint.main(list(args))
    return rc, out.getvalue()


class TestValidInvocations(unittest.TestCase):
    """Correctly documented `aet` invocations produce no findings."""

    def test_valid_fixture_passes(self):
        """A fixture with only valid invocations exits 0 with no findings."""
        rc, out = run_lint("--legacy=warn", str(_FIXTURES / "valid.md"))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("error:", out)
        self.assertNotIn("warning:", out)


class TestRule1Errors(unittest.TestCase):
    """Rule 1: unknown subcommands and flags fail the lint."""

    def test_unknown_subcommand_fails(self):
        rc, out = run_lint("--legacy=warn", str(_FIXTURES / "unknown-subcommand.md"))
        self.assertEqual(rc, 1, out)
        self.assertIn("error: unknown aet subcommand 'bogus-subcommand'", out)

    def test_unknown_flag_fails(self):
        rc, out = run_lint("--legacy=warn", str(_FIXTURES / "unknown-flag.md"))
        self.assertEqual(rc, 1, out)
        self.assertIn("error: unknown flag '--bogus-flag' for 'aet status'", out)

    def test_unknown_state_subcommand_fails(self):
        """Subparser choices are enforced for `aet state <sub>`."""
        rc, out = run_lint("--legacy=warn", str(_FIXTURES / "unknown-flag.md"))
        self.assertIn("error: unknown subcommand 'bogus-substate' for 'aet state'", out)

    def test_placeholder_tokens_pass(self):
        """<...>, $VAR, $(...), ${VAR}, ... pass as opaque values."""
        rc, out = run_lint("--legacy=warn", str(_FIXTURES / "placeholders.md"))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("error:", out)


class TestRule2Legacy(unittest.TestCase):
    """Rule 2: legacy names warn or error per --legacy severity."""

    def test_legacy_names_warn_at_warn_severity(self):
        """Bare legacy names and aet-*/bin paths warn; exit stays 0."""
        rc, out = run_lint("--legacy=warn", str(_FIXTURES / "legacy.md"))
        self.assertEqual(rc, 0, out)
        self.assertIn("warning: legacy command 'aet-work'", out)
        self.assertIn("warning: legacy binary path './aet-work/bin/orchestrator'", out)
        self.assertIn("warning: legacy command 'aet-state'", out)
        self.assertNotIn("error:", out)

    def test_legacy_names_fail_at_error_severity(self):
        rc, out = run_lint("--legacy=error", str(_FIXTURES / "legacy.md"))
        self.assertEqual(rc, 1, out)
        self.assertIn("error: legacy command 'aet-work'", out)

    def test_aet_bootstrap_path_validated_as_aet(self):
        """./aet-work/bin/aet is the binary bootstrap, not a legacy path."""
        rc, out = run_lint("--legacy=error", str(_FIXTURES / "legacy.md"))
        self.assertNotIn("aet-work/bin/aet'", out)


class TestEscapeMarkers(unittest.TestCase):
    """aet-lint off/on HTML comments exempt spans between them."""

    def test_escaped_spans_skipped(self):
        rc, out = run_lint("--legacy=error", str(_FIXTURES / "escaped.md"))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("error:", out)
        self.assertNotIn("warning:", out)

    def test_same_line_escape_pair(self):
        """off/on markers on one line exempt that line, not the next."""
        rc, out = run_lint("--legacy=error", str(_FIXTURES / "escaped-inline.md"))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("error:", out)


class TestRealTreeIntegration(unittest.TestCase):
    """The lint passes over the real repo tree at error severity."""

    def test_real_tree_exits_zero_at_error(self):
        rc, out = run_lint("--legacy=error")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("error:", out)


if __name__ == "__main__":
    unittest.main()
