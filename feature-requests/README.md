# Feature requests — the gap-capture log

This directory is the **gap-capture mechanism** for Layer 1
(`diagnose-and-recommend`). When the recommendation engine diagnoses a product
and finds a needed capability that **neither QA AI KIT nor the tool catalog
covers**, it appends a structured entry here instead of forcing a poor fit or
pretending the gap doesn't exist.

This log is the raw material for two things:
1. **The roadmap** — recurring gaps show what to build next.
2. **The enterprise/paid tier** — capabilities users repeatedly ask for are the
   signal for what's worth charging to build.

## Format

Entries are appended to `log.jsonl` — one JSON object per line (JSONL), so it's
append-only and easy to aggregate. Schema:

```json
{
  "date": "YYYY-MM-DD",
  "product_context": "one-line description of the product that surfaced the gap",
  "missing_capability": "what the kit couldn't do",
  "requested_module": "short slug for the would-be capability, e.g. ios-instruments-perf",
  "diagnosed_risk": "the risk this gap leaves uncovered",
  "candidate_tier": "basic | deep | enterprise",
  "source": "diagnose-and-recommend | auto-discover-recon | manual"
}
```

The `date` is provided by the caller (the skill reads the current date from its
context) — entries are never fabricated with a guessed date.

## Reviewing the log

To see the most-requested gaps (rough, needs `jq`):

```bash
jq -r '.requested_module' feature-requests/log.jsonl | sort | uniq -c | sort -rn
```

## Privacy

Do **not** write confidential product names or internal details into this log —
keep `product_context` generic (e.g. "consumer fitness app with payments"), per
the workspace privacy rules in `CLAUDE.md`.
