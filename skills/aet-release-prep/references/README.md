# aet-release-prep References

## Commit Classification

Commit classification is implemented in `classify_commit()` at
`src/aet/cli/release_prep.py:88-105`, with the prefix and keyword tables at
`src/aet/cli/release_prep.py:16-37`. The behavior is pinned by parametrized
tests in `tests/test_release_prep.py:97-98`.

## PRODUCT.md Template

See [PRODUCT-TEMPLATE.md](PRODUCT-TEMPLATE.md) for a scaffold when creating PRODUCT.md from scratch.

## Edge Cases

See [EDGE-CASES.md](EDGE-CASES.md) for handling no tags, no commits, missing files, and internal-only releases.
