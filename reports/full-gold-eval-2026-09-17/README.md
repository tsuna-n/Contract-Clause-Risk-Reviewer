# Full gold-set evaluation — 17 September 2026

Status: live evaluation running. [results.json](results.json) is updated after
each contract. Final metrics will be written to `metrics.txt` when all 12
contracts finish. The saved per-contract reports permit rescoring without new
model calls.

The set contains 327 clause spans and 82 clauses labelled for classification
and risk. Labels are derived from CUAD annotations; risk labels reflect the
fixture builder's policy mapping, not independent expert assessments.

## Configuration

- Repository revision: `fd52be3e5cf0bdb7d2ffd2fc140bf7fe450491e7`.
- OpenRouter model: `openai/gpt-oss-20b`; the configured `gpt/gpt-oss-20b` was
  invalid in the recorded 7 September benchmark. Override applies only to this
  process; `.env` is unchanged.
- Gemini `gemini-embedding-001`, 768 dimensions; live database playbook of 36
  positions, saved in [playbook.json](playbook.json).
- Judge enabled; clause concurrency 4. Four concurrent live classification
  requests succeeded before starting this run.
- PostgreSQL was started on port 55432 because another application's database
  occupies port 5432. Redis uses the existing project container.
- Source gold, fixture and playbook hashes are stored in `results.json`.

Reproduce from `apps/backend-fastapi`, with the project database available on
55432 and Redis running:

```bash
.venv/bin/python -u -m scripts.full_gold_eval \
  --model openai/gpt-oss-20b --database-port 55432 --concurrency 4 \
  --output ../../reports/full-gold-eval-new
```

This invokes real providers and consumes API quota. Output should use a fresh
directory. The runner saves reports to files and does not create user reports
in the application database.

## Comparison and pass thresholds

The PRD and an explicitly identified Iteration 2 result are not present in the
repository or its tracked file history. Their source documents have been
requested. No baseline deltas or PRD pass verdict can be assigned yet.

The current repository regression test, `tests/eval/test_regression.py`, gates
segmentation F1 at **at least 95%** and citation validity at **100%**. It does
not gate classification or risk accuracy. These are repository thresholds;
they have not been verified against the PRD.

An offline segmentation check already completed on all 12 contracts with F1
100% per contract: [offline-segmentation.json](offline-segmentation.json).
Gold boundaries were generated with the same segmenter, so this checks
consistency with the fixtures, not independent segmentation quality.

Citation validity checks whether returned IDs exist in the playbook. It does
not measure excerpt grounding, the correctness of the rationale, or clauses
that produced no citations. Grounding pass counts and pipeline failure counts
are therefore reported separately.

Historical classification/risk numbers before the 30 July relabelling cannot
be compared directly with this gold set. A smaller historical cohort also
needs the corresponding subset rescored before computing a baseline delta.

## Validation

- Metrics and eval harness tests: 16 passed.
- Runner Ruff lint and formatting checks: passed.
- Live four-request structured-output preflight: passed.
