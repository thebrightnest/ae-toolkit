"""Tests for src/aet/test_runners.py — the shared test-runner registry.

One registry serves both wirelog detection (``is_test_command``) and telemetry
scope classification (``classify_test_scope``): a command the detector
recognises is classifiable by construction.
"""

import unittest

from aet import telemetry, test_runners, wirelog


class TestResolveNormalisation(unittest.TestCase):
    """The normalisation pipeline applied before matching."""

    def test_detects_test_command_after_cd_and_separator(self):
        resolved = test_runners.resolve_test_command("cd /path/to/wt && make validate")
        self.assertIsNotNone(resolved)
        runner, _args = resolved
        self.assertEqual(runner, "make")
        self.assertTrue(wirelog.is_test_command("cd /path/to/wt && make validate"))
        self.assertTrue(wirelog.is_test_command("cd proj && python3 -m pytest -q"))

    def test_detects_test_command_after_source_and_dot_prefixes(self):
        self.assertTrue(wirelog.is_test_command("source .venv/bin/activate && pytest"))
        self.assertTrue(wirelog.is_test_command(". ./env/bin/activate && make test"))

    def test_detects_test_command_with_leading_env_assignments(self):
        resolved = test_runners.resolve_test_command("CI=true pytest tests/")
        self.assertIsNotNone(resolved)
        runner, args = resolved
        self.assertEqual(runner, "pytest")
        self.assertEqual(args, ["tests/"])
        self.assertTrue(wirelog.is_test_command("CI=true DEBUG=1 make test"))

    def test_detects_test_command_with_interpreter_path_prefix(self):
        cases = {
            ".venv/bin/python -m pytest": "python -m pytest",
            ".venv/bin/pytest tests/": "pytest",
            "./vendor/bin/phpunit": "phpunit",
            "/usr/local/bin/vitest run": "vitest",
        }
        for command, expected_runner in cases.items():
            with self.subTest(command=command):
                resolved = test_runners.resolve_test_command(command)
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved[0], expected_runner)

    def test_detects_test_command_behind_wrapper(self):
        cases = {
            "poetry run pytest tests/": ("pytest", ["tests/"]),
            "uv run pytest": ("pytest", []),
            "npx vitest run": ("vitest", ["run"]),
            "npx -y jest": ("jest", []),
            "npm run test": ("npm test", []),
            "yarn test": ("yarn test", []),
            "pnpm test": ("pnpm test", []),
            "bundle exec rspec spec/models/foo_spec.rb": ("rspec", ["spec/models/foo_spec.rb"]),
            "time make test": ("make", []),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                resolved = test_runners.resolve_test_command(command)
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved, expected)

    def test_does_not_detect_runner_mentioned_in_unrelated_command(self):
        for command in (
            "grep -r pytest .",
            'git commit -m "fix pytest"',
            'echo "run pytest"',
            "git log --oneline | grep pytest",
            "pytester --help",
            "make testify",
            "./run_tests.sh",
            "",
        ):
            with self.subTest(command=command):
                self.assertIsNone(test_runners.resolve_test_command(command))
                self.assertFalse(wirelog.is_test_command(command))


class TestNewRunners(unittest.TestCase):
    """R-2: the six runners added on top of the v1 eight."""

    def test_each_new_runner_is_detected_and_classified(self):
        bare = (
            "rspec",
            "phpunit",
            "php artisan test",
            "dotnet test",
            "gradle test",
            "python -m unittest",
        )
        for command in bare:
            with self.subTest(command=command):
                self.assertIsNotNone(test_runners.resolve_test_command(command))
                self.assertTrue(wirelog.is_test_command(command))
                self.assertEqual(telemetry.classify_test_scope(command), "full-suite")

        impact = (
            "rspec spec/models/foo_spec.rb",
            "phpunit tests/Unit/FooTest.php",
            "php artisan test tests/Feature/LoginTest.php",
            "dotnet test tests/FooTests/FooTests.csproj",
            "python -m unittest discover -s tests/unit",
        )
        for command in impact:
            with self.subTest(command=command):
                self.assertTrue(wirelog.is_test_command(command))
                self.assertEqual(telemetry.classify_test_scope(command), "impact")


class TestSingleRegistryProof(unittest.TestCase):
    """R-3: detection and classification read one parse, not two lists."""

    def test_registry_removal_breaks_both_detection_and_classification(self):
        real = test_runners.resolve_test_command
        try:
            test_runners.resolve_test_command = lambda _command: None
            self.assertFalse(wirelog.is_test_command("pytest"))
            self.assertEqual(telemetry.classify_test_scope("pytest"), "unknown")
        finally:
            test_runners.resolve_test_command = real
        # Restored: both sides recognise the command again.
        self.assertTrue(wirelog.is_test_command("pytest"))
        self.assertEqual(telemetry.classify_test_scope("pytest"), "full-suite")


if __name__ == "__main__":
    unittest.main()
