# Retro: `aet-evolve` consumes `aet metrics`

**Date:** 2026-07-20
**Plan:** `docs/plans/tll-04-evolve-metrics-learning-loop.md`
**Trigger:** Phase 7a exit gate — run one real `aet-evolve` cycle that consumes the `aet metrics` CLI surface (tll-03).

## Metrics Evidence

Commands run:

```bash
aet metrics --json --history-file /Users/pedrorocha/Sites/aiskills/.agents/work-history.jsonl
aet metrics --json --history-file /Users/pedrorocha/Sites/aiskills/.agents/work-history.jsonl --since 2026-07-19
```

Results (all time):

```json
{
  "since": null,
  "overall": {
    "settled": 257,
    "merged": 254,
    "first_pass": 0,
    "first_pass_rate": 0.0,
    "rework": 383,
    "cost": {
      "tokens_total": 499764347,
      "tokens_avg_per_merged": 1967576.1692913387,
      "usd_total": null,
      "usd_avg_per_merged": null,
      "usd_known_tasks": 0
    }
  },
  "classes": {
    "unclassified": {
      "settled": 257,
      "merged": 254,
      "first_pass": 0,
      "first_pass_rate": 0.0,
      "rework": 383,
      "cost": {
        "tokens_total": 499764347,
        "tokens_avg_per_merged": 1967576.1692913387,
        "usd_total": null,
        "usd_avg_per_merged": null,
        "usd_known_tasks": 0
      }
    }
  }
}
```

Results since the previous retro (`2026-07-19`):

```json
{
  "since": "2026-07-19",
  "overall": {
    "settled": 9,
    "merged": 9,
    "first_pass": 0,
    "first_pass_rate": 0.0,
    "rework": 166,
    "cost": {
      "tokens_total": 42584308,
      "tokens_avg_per_merged": 4731589.777777778,
      "usd_total": null,
      "usd_avg_per_merged": null,
      "usd_known_tasks": 0
    }
  },
  "classes": {
    "unclassified": {
      "settled": 9,
      "merged": 9,
      "first_pass": 0,
      "first_pass_rate": 0.0,
      "rework": 166,
      "cost": {
        "tokens_total": 42584308,
        "tokens_avg_per_merged": 4731589.777777778,
        "usd_total": null,
        "usd_avg_per_merged": null,
        "usd_known_tasks": 0
      }
    }
  }
}
```

## Findings

1. **First-pass merge rate is 0.0%** across all 254 merged tasks (and all 9 tasks since the last retro). Every merged task carried measurable rework.
2. **Average cost per merged task is ~2.0 M tokens** overall and ~4.7 M tokens in the last day. USD cost is unavailable because cost estimates are not recorded in the telemetry used.
3. **Class breakdown is entirely `unclassified`.** `aet metrics` buckets by `work_class`, but `work-history.jsonl` does not currently preserve the `work_class` (or `size`) values read from plan frontmatter by `plan_parser.py`. As a result, the per-class view cannot distinguish trivial, normal, or critical work, which limits the metrics' ability to localize high-rework patterns.

## Routed Actions

### AET-level (toolkit)

- **No `aet-evolve` skill edit is warranted beyond the change made in this cycle.** The retro procedure now includes the metrics evidence step (`aet metrics --json`, scoped with `--since`), which satisfies the phase 7a exit gate (R-7).
- **Follow-up queued:** preserve `work_class` and `size` in `work-history.jsonl` records so future `aet metrics` runs can produce a meaningful per-class breakdown. Until then, the class split will remain unclassified and the metrics evidence step will only inform aggregate trends, not targeted `system-evolve` edits.

### Project-level (this repo)

- None. The skill and reference updates are part of this plan's implementation.

## Conclusion

The learning loop ran on real data. The numbers confirm that rework is universal (0% first-pass rate) and that the class dimension of `aet metrics` is currently blocked by missing metadata in the work-history pipeline. The immediate change is to wire `aet metrics` into `aet retro`; the next cycle should be able to act on per-class metrics once the metadata gap is closed.
