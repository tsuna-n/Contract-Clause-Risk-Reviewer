"""The AI review engine.

Reading order follows the pipeline:

``llm.py`` (talk to Gemini) -> ``retrieval.py`` (find playbook positions) ->
``agents.py`` (one class per pipeline step) -> ``guardrails.py`` (reject
ungrounded output) -> ``pipeline.py`` (run the steps over a document).
"""
