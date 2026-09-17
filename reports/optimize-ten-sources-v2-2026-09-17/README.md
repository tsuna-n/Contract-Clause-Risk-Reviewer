# Completed canonical-source scoring experiment

This historical experiment completed all 10 fixtures (281 clauses) in 189.32 seconds.

Classification agreement: 65.28%; risk agreement: 51.39%.
Pipeline failures: 0; unknown risks: 119; verified reviews: 159.

The scorer selects IDs constrained to retrieved positions; the application copies canonical citation and fallback wording. A known ID alone does not prove the risk assessment is correct. Semantic judge feedback is preserved as `verification_reason`.

This is not the current source or configuration. Source hashes and settings for this experiment are in `results.json`; later changes refine retrieval, risk coverage, explicit contract references and calendar durations. See [the final optimization report](../optimization-2026-09-17.md).

Running `scripts.full_gold_eval` now uses the current source, not the historical v2 prompts. Full comparisons use matching fixture, playbook and gold hashes without modifying gold labels. The original DeepSeek/concurrency-1 snapshot has an incomplete baseline and cannot establish full baseline accuracy.
