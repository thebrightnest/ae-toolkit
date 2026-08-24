"""Deriving which tests cover which source files, from the source itself."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import test_deps


class _Repo:
    """A throwaway repo with a src package and a tests tree."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "src" / "aet").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "scripts").mkdir()

    def src(self, rel: str, text: str = "") -> None:
        path = self.root / "src" / "aet" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test(self, rel: str, text: str = "") -> None:
        path = self.root / "tests" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def script(self, rel: str, text: str = "") -> None:
        path = self.root / "scripts" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def map(self) -> test_deps.DependencyMap:
        return test_deps.DependencyMap(self.root)


class TestDerivation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = _Repo(Path(self.tmp.name).resolve())

    def tearDown(self):
        self.tmp.cleanup()

    def test_an_importing_test_covers_the_module(self):
        self.repo.src("foo.py")
        self.repo.test("test_foo.py", "from aet import foo\n")

        self.assertEqual(
            self.repo.map().tests_for("src/aet/foo.py"), ["tests/test_foo.py"]
        )

    def test_the_test_file_name_does_not_have_to_match(self):
        """The rule this replaced required tests/test_<module>.py by name."""
        self.repo.src("foo.py")
        self.repo.test("test_something_else.py", "import aet.foo\n")

        self.assertEqual(
            self.repo.map().tests_for("src/aet/foo.py"),
            ["tests/test_something_else.py"],
        )

    def test_a_symbol_import_resolves_to_its_module(self):
        self.repo.src("foo.py", "BAR = 1\n")
        self.repo.test("test_foo.py", "from aet.foo import BAR\n")

        self.assertEqual(
            self.repo.map().tests_for("src/aet/foo.py"), ["tests/test_foo.py"]
        )

    def test_coverage_follows_imports_transitively(self):
        """A test driving an entry point exercises what the entry point reaches."""
        self.repo.src("leaf.py")
        self.repo.src("entry.py", "from aet import leaf\n")
        self.repo.test("test_entry.py", "from aet import entry\n")

        self.assertEqual(
            self.repo.map().tests_for("src/aet/leaf.py"), ["tests/test_entry.py"]
        )

    def test_an_import_cycle_does_not_hang(self):
        self.repo.src("a.py", "from aet import b\n")
        self.repo.src("b.py", "from aet import a\n")
        self.repo.test("test_a.py", "from aet import a\n")

        self.assertEqual(self.repo.map().tests_for("src/aet/b.py"), ["tests/test_a.py"])

    def test_a_quoted_filename_counts_as_a_reference(self):
        """68 of 161 test files load a CLI module through SourceFileLoader."""
        self.repo.src("cli/orchestrator.py")
        self.repo.test(
            "test_orch.py",
            'BIN = ROOT / "src" / "aet" / "cli" / "orchestrator.py"\n',
        )

        self.assertEqual(
            self.repo.map().tests_for("src/aet/cli/orchestrator.py"),
            ["tests/test_orch.py"],
        )

    def test_a_script_is_reached_by_the_test_that_names_its_path(self):
        """Fixture names avoid the real repo's, which this file would then claim."""
        self.repo.script("bootstrap-fixture.sh", "#!/bin/sh\n")
        self.repo.test(
            "test_bootstrap.py", 'run(["sh", "scripts/bootstrap-fixture.sh"])\n'
        )

        self.assertEqual(
            self.repo.map().tests_for("scripts/bootstrap-fixture.sh"),
            ["tests/test_bootstrap.py"],
        )

    def test_a_script_named_by_basename_alone_is_not_claimed(self):
        """A basename quoted in an unrelated fixture must not claim the real file."""
        self.repo.script("bootstrap-fixture.sh", "#!/bin/sh\n")
        self.repo.test("test_elsewhere.py", '"bootstrap-fixture.sh"\n')

        self.assertEqual(
            self.repo.map().tests_for("scripts/bootstrap-fixture.sh"), []
        )

    def test_a_quoted_name_matching_nothing_contributes_nothing(self):
        self.repo.src("foo.py")
        self.repo.test("test_foo.py", '"not_a_module.py"\n')

        self.assertEqual(self.repo.map().tests_for("src/aet/foo.py"), [])

    def test_an_unreached_module_returns_an_empty_list(self):
        """Empty is the caller's cue to run everything, not nothing."""
        self.repo.src("orphan.py")
        self.repo.test("test_other.py", "x = 1\n")

        self.assertEqual(self.repo.map().tests_for("src/aet/orphan.py"), [])

    def test_an_unparseable_test_file_still_yields_its_literals(self):
        self.repo.src("cli/orchestrator.py")
        self.repo.test("test_broken.py", 'def f(:\n    "orchestrator.py"\n')

        self.assertEqual(
            self.repo.map().tests_for("src/aet/cli/orchestrator.py"),
            ["tests/test_broken.py"],
        )

    def test_a_third_party_import_is_ignored(self):
        self.repo.src("foo.py")
        self.repo.test("test_foo.py", "import pytest\nimport json\n")

        self.assertEqual(self.repo.map().tests_for("src/aet/foo.py"), [])

    def test_an_unknown_source_path_returns_an_empty_list(self):
        self.repo.src("foo.py")

        self.assertEqual(self.repo.map().tests_for("src/aet/nope.py"), [])

    def test_modules_and_test_files_are_enumerable(self):
        self.repo.src("foo.py")
        self.repo.script("run-fixture.sh")
        self.repo.test("test_foo.py", "from aet import foo\n")

        dep_map = self.repo.map()

        self.assertIn("src/aet/foo.py", dep_map.modules)
        self.assertIn("scripts/run-fixture.sh", dep_map.modules)
        self.assertEqual(dep_map.test_files, ["tests/test_foo.py"])


class TestCacheIdentity(unittest.TestCase):
    def test_the_same_root_returns_the_same_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _Repo(root)
            subprocess.run(["git", "init", "-q", str(root)], check=True)

            self.assertIs(
                test_deps.dependency_map(str(root)), test_deps.dependency_map(str(root))
            )


if __name__ == "__main__":
    unittest.main()
