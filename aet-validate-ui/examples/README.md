# Examples for aet-validate-ui

## Example 1: Manual validation

```
aet-validate-ui on docs/plans/checkout-redesign-plan.md
```

The skill reads the plan, checks all 7 categories, and prints a gap report to stdout.

## Example 2: Pipeline integration

When running `aet-pipeline-plan`, the pipeline automatically calls `validate-pipeline` after PRD creation. The UI gap report path is appended to the PRD footer.

## Example 3: Skip validation

If the PRD includes a "no UI" marker (e.g., "This is an API-only feature with no user interface"), the skill prints a skip reason and exits:

```
⏭ Skipping UI validation — PRD is marked as "no UI."
```
