# aet-release-prep References

## Commit Classification

Commit classification is implemented in `classify_commit()` at
`src/aet/cli/release_prep.py:347`, with the prefix and keyword tables at
`src/aet/cli/release_prep.py:41-62`. The behavior is pinned by parametrized
tests in `tests/test_release_prep.py:98`.

## PRODUCT.md Template

See [PRODUCT-TEMPLATE.md](PRODUCT-TEMPLATE.md) for a scaffold when creating PRODUCT.md from scratch.

## Configuration

See [CONFIG.md](CONFIG.md) for the `release_prep` section of
`.agents/aet-config.json` — which resolutions it overrides, and how each one is
auto-detected when absent.

## Edge Cases

See [EDGE-CASES.md](EDGE-CASES.md) for handling unreachable tags, bootstrap
runs, dated projects, no commits, missing files, and internal-only releases.
