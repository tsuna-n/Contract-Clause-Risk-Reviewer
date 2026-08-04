"""Application settings + feature flags (pydantic-settings)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration — the single source of truth.

    Values are loaded from ``.env`` (see ``.env.example``). Extra keys are
    ignored so the same file can be shared with other tooling. Fields without
    a default are required: the app refuses to boot rather than run with a
    missing database URL or a placeholder signing key.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- core ---
    database_url: str
    app_env: str = "development"
    # Origin of the frontend: doubles as the CORS allow-list and as the
    # redirect target after a successful OAuth callback.
    frontend_url: str = "http://localhost:5173"

    # --- upload limits ---
    # The route used to read an upload whole with no ceiling at all, so a large
    # file was both a memory spike and, once segmented, hours of LLM calls.
    # Two separate limits because they fail differently: bytes protect the
    # process, clause count protects the bill.
    max_upload_bytes: int = 10 * 1024 * 1024
    # ~300 clauses is far above any contract in the CUAD gold set (the largest
    # is 47) and still an order of magnitude below "someone uploaded a book".
    # At roughly four LLM calls and 22 seconds per clause, the cap is really a
    # statement about how long one request may run.
    max_clauses: int = 300

    # --- auth: Google OAuth + JWT ---
    google_oauth_api: str
    google_key_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    session_secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    # ``/auth/dev-login`` issues a token for whatever email is asked for, which
    # is what makes testing over LAN possible at all (Google refuses redirect
    # URIs on private IPs). It needs two locks, not one: ``APP_ENV`` is the
    # setting most likely to be left at its default by the deploy that matters,
    # and a single forgotten variable should not be the difference between a
    # login page and an open door. Both this and ``APP_ENV=development`` must
    # hold, so production has to make two mistakes to be exposed.
    enable_dev_login: bool = False
    # Who may write to the playbook (create/update/delete). Comma-separated
    # emails; empty means every signed-in reviewer may, which is the behaviour a
    # single-team deployment already had and the one its ``/playbook`` page
    # expects.
    #
    # Reading stays open to any signed-in user either way. The asymmetry is the
    # point: a playbook position is what the judge grounds citations against, so
    # editing one edits every verdict the system will reach afterwards - that is
    # worth naming the people who can do it, without inventing a role system and
    # a migration for a team of one.
    playbook_admin_emails: str = ""
    # One working day. Logout is client-side only (the token stays valid until
    # it expires), so this is also how long a leaked token keeps working —
    # which is why it isn't set to weeks.
    access_token_expire_minutes: int = 60 * 12

    # --- llm ---
    # Which vendor answers the review. Everything else in this block is
    # resolved per provider (see ``app/ai/providers.py``), so moving between
    # Gemini, Claude, and any OpenAI-compatible host - Z.AI's GLM models,
    # DeepSeek, a local vLLM - is an ``.env`` edit, not a code change.
    llm_provider: str = "gemini"  # gemini | anthropic | openai | zai
    # ``None`` means "the provider's default model"; ``openai`` has no default
    # and requires this to be set.
    llm_model: str | None = None
    # One key to override them all. Left unset, each provider reads its own
    # conventional variable below - which is what the SDKs and every other tool
    # on the machine already expect.
    llm_api_key: str | None = None
    gemini_api_key: str | None = None  # read from $GEMINI_API_KEY
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    zai_api_key: str | None = None
    # Only meaningful for OpenAI-compatible hosts; ``zai`` fills its own in.
    llm_base_url: str | None = None
    # Per-call ceiling, not per-review: one review fans out to dozens of calls
    # (segment, then classify/match/score/judge for every clause). Without it
    # a single hung call pins a worker forever. The orchestrator already
    # isolates a failed clause, so a timeout degrades that clause to
    # "needs manual review" instead of sinking the whole report.
    llm_timeout_seconds: int = 120
    # Whether a reasoning model may think before answering, on
    # OpenAI-compatible hosts that expose the switch (Z.AI's GLM models do).
    #
    # Defaults to off because reasoning tokens come out of the same
    # ``max_tokens`` budget as the answer: a model that thinks past the budget
    # returns a 200 with empty ``content``, which is exactly how three clauses
    # were lost in the 2026-07-30 eval run. Measured on GLM-4.6 with one of the
    # scoring prompts, the same call took 23.7s / 984 output tokens thinking and
    # 2.1s / 55 without. ``auto`` restores the model's own default for a host
    # where the extra reasoning is worth the latency and the failure mode.
    llm_thinking: Literal["auto", "disabled"] = "disabled"
    # How many times one logical call may be attempted before the clause is
    # given up on. Retries cover exactly the failures a second attempt can
    # survive - a timeout, a 429/5xx, an empty answer (see
    # ``providers.is_transient``) - never a 400 or a bad key.
    llm_max_attempts: int = 3
    # First backoff, doubling per attempt. Deliberately short: the retry budget
    # is wall clock the reviewer is already waiting through, not a background
    # queue.
    llm_retry_backoff_seconds: float = 1.0
    # How many clauses the orchestrator reviews at once. Each clause is 3-4
    # independent LLM calls in sequence (classify, match, score, judge) and
    # network latency dominates every one of them, so running several clauses'
    # calls concurrently can cut wall clock roughly by this factor instead of
    # summing every clause serially - *if* the vendor's rate limit tolerates
    # it.
    #
    # Defaults to 1 (no induced concurrency beyond the one dedicated slot
    # metadata extraction always gets) because it doesn't, here: live-tested
    # 2026-08-04 against this project's paid Z.AI glm-4.7 key with a 3-clause
    # contract, concurrency=2 and concurrency=4 both tripped its per-request
    # rate limit (``code 1302``) hard enough that a clause exhausted its
    # retries and degraded to ``unknown`` - a worse outcome than the extra
    # wall clock it was spent chasing. Only raise this after confirming the
    # configured provider's actual rate limit can take it; a vendor with a
    # generous per-second budget (or a higher paid tier) is exactly what this
    # setting is for.
    review_concurrency: int = 1

    # --- rag / storage ---
    redis_url: str = "redis://localhost:6379/0"
    # Embeddings are configured separately from chat because the two don't have
    # to come from the same vendor - and with Claude they can't, since
    # Anthropic has no embedding API. Unset means "follow ``llm_provider`` if it
    # can embed, otherwise Gemini".
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    # Must match the ``vector`` column width in the Alembic migration. Changing
    # it needs a new migration *and* a re-ingest of the playbook: vectors from
    # two different models aren't comparable, and a length mismatch is stored
    # as a zero vector rather than rejected.
    embedding_dim: int = 768
    # Reuse vectors for text already embedded instead of asking again. Worth a
    # flag because it is the difference between one embedding request per
    # review and one per clause: the free tiers that make this project cheap to
    # run count *requests*, so re-reviewing a contract, or a second eval pass
    # over the same fixtures, otherwise spends quota on answers already known.
    enable_embedding_cache: bool = True
    # A vector is a pure function of (provider, model, dim, text) and the key
    # carries all four, so entries never go stale - the TTL is only here to
    # keep Redis from growing without bound.
    embedding_cache_ttl_seconds: int = 60 * 60 * 24 * 7

    # --- feature flags ---
    enable_judge: bool = True
    enable_hybrid_retrieval: bool = True
    # One extra LLM call per review (not per clause) that reads the parties,
    # dates, value and governing law off the document. Off means reports carry
    # empty metadata and the UI shows no header panel — nothing else changes.
    enable_metadata_extraction: bool = True
    # Where finished reports live. ``postgres`` keeps them until their owner
    # deletes them, which is what makes the history list a record rather than
    # a recent-items list; ``redis`` restores the old TTL'd behaviour for a
    # deployment that would rather not retain contract text at all.
    #
    # A ``Literal``, not a plain string, so a typo fails at boot: the two
    # choices differ in whether contract text is retained indefinitely, and
    # ``REPORT_STORAGE=redis1`` quietly falling back to the default would be a
    # retention decision made by a slip of the finger.
    report_storage: Literal["postgres", "redis"] = "postgres"
    # How long a finished report stays in Redis (``REPORT_STORAGE=redis``
    # only). Overriding a clause reloads the report by id, so this is really
    # "how long can someone step away and still adjust their results" — an
    # hour was short enough to 404 on people mid-session. Kept below the token
    # lifetime so the session always outlives the data it points at.
    retention_ttl_seconds: int = 60 * 60 * 8
    # How long a stored report may be kept (``REPORT_STORAGE=postgres``).
    # ``None`` — the default — means "until its owner deletes it", which is the
    # behaviour that makes history a record of everything a reviewer has run.
    #
    # This is the policy, not the mechanism: nothing in the request path reads
    # it, because deleting other people's data is not something an upload should
    # do on the way past. ``python -m scripts.purge_reports`` enforces it, and
    # until that is scheduled (cron, a systemd timer) setting this deletes
    # nothing.
    report_retention_days: int | None = None

    @property
    def playbook_admins(self) -> frozenset[str]:
        """:attr:`playbook_admin_emails` as a set, lowercased.

        Case-folded because an allow-list that misses when someone types their
        own address in capitals is a lock that only catches its owner.
        """
        return frozenset(
            email.strip().lower()
            for email in self.playbook_admin_emails.split(",")
            if email.strip()
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()  # type: ignore[call-arg]
