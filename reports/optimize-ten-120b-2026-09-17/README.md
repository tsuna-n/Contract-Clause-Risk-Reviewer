# Ten-contract optimization evaluation

Candidate evaluation completed. `results.json` records every completed
contract, source hashes, fixture hashes, configuration and final metrics.
This run covers the first ten CUAD fixtures: 281 clauses, 72 labelled clauses.

The candidate completed in **253.26 seconds (4 minutes 13 seconds)** with zero
pipeline failures. Classification accuracy is **68.06%**, risk accuracy **44.44%**,
segmentation F1 **100%**, and all **304 citation IDs** are valid. **149/281**
assessments passed grounding verification; four clauses have unknown risk.
These results establish speed and execution reliability, but risk accuracy and
grounding remain too weak to declare the optimization goal achieved. The model
and concurrency overrides have therefore not been persisted to `.env`.

Validation: 230 unit tests and 70 integration tests passed; changed-file Ruff
lint/format and `git diff --check` passed. Integration tests require execution
outside this session's sandbox because TestClient stalls inside it.

Changes under evaluation:

- OpenRouter routing requires support for the requested JSON Schema.
- Invalid responses cannot downgrade subsequent requests to JSON-object mode.
- Reasoning uses the OpenRouter parameter; mandatory reasoning falls back to
  low effort. Concurrent capability errors are handled independently.
- SDK retries are disabled; the application owns the retry budget.
- The judge sees complete cited playbook positions and the suggested fallback.
  An assessment without citations cannot receive a verified badge.
- The evaluation scorer counts missing or nonoverlapping labelled clauses as
  errors, rather than dropping them from the accuracy denominator.

Candidate configuration uses `openai/gpt-oss-120b`, Groq/Cerebras endpoints,
four clause workers, and the existing OpenRouter Gemini embedding configuration.
The judge remains enabled. API calls use real quota.

Reproduce from `apps/backend-fastapi`, with PostgreSQL on 55432 and Redis ready:

```bash
.venv/bin/python -u -m scripts.full_gold_eval \
  --model openai/gpt-oss-120b --openrouter-providers Groq Cerebras \
  --database-port 55432 --concurrency 4 --limit 10 \
  --output ../../reports/optimize-ten-new
```

To rescore saved reports without model calls:

```bash
.venv/bin/python -m scripts.compare_saved_evals \
  --baseline ../../reports/baseline-ten-deepseek-2026-09-17 \
  --candidate ../../reports/optimize-ten-120b-2026-09-17 \
  --output ../../reports/ten-contract-comparison-2026-09-17.json
```

Historical results in `full-gold-eval-2026-09-17` contain only three completed
contracts and used direct Gemini embeddings. `partial-comparison.json` identifies
that narrower cohort and its different configuration; it is not a complete
ten-contract comparison. The current application setting was inspected directly:
`deepseek/deepseek-v4.1-flash`, one clause worker. A fresh baseline will run this
configuration using the app source snapshot from revision `68ada1c`, taken before
these edits, with the same fixtures, playbook and embedding provider. Concurrency
and model changes are intentional parts of the optimization and are recorded
explicitly in the comparison.

Gold classification labels are derived from CUAD annotations and risk labels
from the fixture builder's category-to-policy mapping. Accuracy against these
labels is a regression measure, not independent expert validation. Segmentation
fixtures were built using the same segmenter, and citation validity checks IDs;
grounding verification and pipeline failures are counted separately.

OpenRouter references: [structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
and [reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
