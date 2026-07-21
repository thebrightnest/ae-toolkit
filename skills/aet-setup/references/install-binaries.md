# Installing the `aet` Dispatcher

The AE Toolkit skills invoke helper commands through the `aet` dispatcher (`aet state`, `aet run`, `aet mine-learnings`, etc.). This page explains how to put it on `PATH`.

## Important prerequisite

`npx skills` copies skill markdown to your agent's skills directory; it does **not** install the Python CLI. The `aet` command is a Python console script, so you must install the `aet` package first.

## Procedure

1. Install the `aet` Python package if it is not already present:

   ```bash
   pip install git+https://github.com/thebrightnest/ae-toolkit.git@v1.3.0
   ```

   For local development, clone the repo and install editable:

   ```bash
   git clone https://github.com/thebrightnest/ae-toolkit.git
   cd ae-toolkit
   pip install -e ".[dev]"
   ```

2. Run the installer:

   ```bash
   aet install
   ```

   It symlinks `aet` into `~/.local/bin` (override with `AET_BIN_DIR`) and prunes retired legacy binary names.

3. Verify the dispatcher is available:

   ```bash
   command -v aet
   ```

4. If `~/.local/bin` is not on `PATH`, add it to your shell profile.

## When to use

- After installing skills via `npx skills`
- When another AET skill reports that a helper binary is not on `PATH`
- When setting up a new machine
