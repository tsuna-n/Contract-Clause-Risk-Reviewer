# Contract review optimization

Current local configuration follows the user's final selection:
`deepseek/deepseek-v4.1-flash` through OpenRouter, eight clause workers,
unrestricted endpoint routing, reasoning disabled where supported, and judge enabled.
GPT-OSS-120B is no longer the selected model. Local Postgres uses port 55432;
the unrelated database on port 5432 is unchanged. Credentials were preserved.

All completed runs below cover the same ten contracts, 281 clauses and 72
labelled clauses, with unchanged fixture, gold and playbook data.

| Completed experiment | Time | Classification agreement | Risk agreement | Failed clauses |
|---|---:|---:|---:|---:|
| First GPT-OSS candidate | 253.26 s | 68.06% | 44.44% | 0 |
| DeepSeek, scorer v3, retrieval 5, four workers | 982.64 s | 76.39% | 52.78% | 0 |
| GPT-OSS, scorer v5, retrieval 8, referenced context | 193.57 s | 70.83% | 63.89% | 0 |
| Selected DeepSeek, scorer v6 / judge v5, retrieval 8, eight workers | 373.72 s | 77.78% | 59.72% | 0 |

The DeepSeek result is in
[its saved manifest](optimize-ten-deepseek-v3-2026-09-17/results.json).
The later GPT-OSS result is a historical experiment, in
[its saved manifest](optimize-ten-final-2026-09-17/results.json).
The selected DeepSeek pipeline completed all ten contracts with the latest
context/calendar prompts; the GPT-OSS figures do not describe current DeepSeek quality.
The initial latest-DeepSeek verification was
[interrupted](optimize-ten-deepseek-final-2026-09-18/results.json) after a confirmed
prompt regression: calendar-duration guidance caused irrelevant 90-day discussion
in a monthly impression commitment and unnecessarily long rationale. Scorer v6
and judge v5 restrict that comparison to applicable durations, distinguish minimum
commitments from exposure caps, and request concise explanations.
The corrected pipeline completed all ten fixtures with eight workers in
[`optimize-ten-deepseek-v6-c8-2026-09-18`](optimize-ten-deepseek-v6-c8-2026-09-18/results.json).
Eight workers are now saved in `.env`; a fresh settings/LLM/orchestrator construction
matches the completed benchmark. Partial runs were excluded from final comparison.
The [full matched comparison](deepseek-v3-vs-v6-c8-2026-09-18.json) rescores both
complete DeepSeek runs using unchanged gold, fixtures and playbook: latency is 2.63x
faster, classification agreement rises 1.39 percentage points, and risk agreement
rises 6.94 percentage points. Both are measured single runs, not a significance test
or SLA; embedding cache was enabled.

The original unchanged DeepSeek/concurrency-1 snapshot completed only the shortest
eight-clause contract in 611.92 seconds. It repeatedly exhausted output tokens
while reasoning and returned empty responses. That obsolete benchmark was stopped;
[its manifest](baseline-ten-deepseek-2026-09-17/results.json) is explicitly incomplete.
Full original-baseline accuracy and speedup are unknown.

The implementation uses OpenRouter's reasoning parameters, maintains strict schemas,
avoids SDK retries nested inside application retries, constrains citation IDs to
retrieved positions and copies quotes/fallbacks from canonical sources. Retrieval
preserves subject policies alongside secondary subjects. Explicit contract references
resolve to bounded, verbatim excerpts with source spans; ambiguous references are
not guessed. Scorer and judge distinguish calendar months from fixed-day windows.
Reports preserve the final judge reason.

The sell-off regression resolves Appendix 2 and its explicit three-month duration.
The selected DeepSeek judge rejected the final clause-7.5 rationale for conflating
sell-off and transition-assistance obligations and calling a defined scope indefinite;
the report correctly leaves that assessment unverified. The appendix assessment
explicitly separates the two obligations instead of treating three months as a
90-day transition window. The monthly-impressions rationale is 58 words, omits the
unrelated calendar discussion, and distinguishes the minimum volume from a liability cap.

Gold risk labels are generated from CUAD category mappings, not independent expert
legal judgments. Segmentation gold comes from the same segmenter. Valid citation IDs
do not establish semantic correctness. The completed DeepSeek run left 106/281 risks
unknown and verified 175/281 reviews; the selected latest DeepSeek run left 115/281
unknown and verified 163/281. Accuracy improved while abstention increased, so unknown
and unverified assessments still require human review.

The [completion audit](optimize-ten-deepseek-v6-c8-2026-09-18/completion-audit.json)
checks all ten saved reports against the current source hashes and saved settings.
All 168 cited assessments pass deterministic source/fallback checks, every quote is
canonical playbook text, all 40 referenced excerpts match their fixture spans, and
no uncited assessment is marked verified. There are 281/281 valid citation IDs and
zero pipeline failures. Rationale length is median 49 words, maximum 85 words.

Validation: the latest changes passed 248 unit tests and 70 integration tests
(318 total) with the selected DeepSeek settings. Ruff lint/format and
`git diff --check` passed. Settings and the constructed LLM client were checked
after the user's model change and both select DeepSeek with an empty endpoint list.
These include an empty BM25 corpus regression: policies reduced entirely to stopwords now retain dense
retrieval instead of dividing by zero.

To evaluate the current saved configuration from `apps/backend-fastapi`, with the
project database and Redis running, use a fresh output directory:

```bash
.venv/bin/python -u -m scripts.full_gold_eval \
  --limit 10 --output ../../reports/deepseek-current-new
```

The runner makes real API calls and saves per-contract reports, final metrics,
source hashes, settings and fixture/playbook/gold hashes. Saved reports can be
compared without model calls using `scripts.compare_saved_evals`.
