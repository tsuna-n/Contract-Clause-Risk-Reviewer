"""CLI: delete stored reports past the retention window.

Usage:
    python -m scripts.purge_reports --older-than-days 90
    python -m scripts.purge_reports --dry-run          # count first, delete never
    python -m scripts.purge_reports                    # uses REPORT_RETENTION_DAYS

Stored reports do not expire: ``REPORT_STORAGE=postgres`` keeps a review until
its owner deletes it, which is the behaviour that makes the history sidebar a
record rather than a recent-items list. A deployment that has to promise "we
don't keep contract text beyond N days" therefore needs this run on a schedule —
nothing in the app calls it, and no upload sweeps other people's data on the way
past. A cron entry is the whole mechanism:

    # 03:15 daily, honouring REPORT_RETENTION_DAYS from .env
    15 3 * * * cd /srv/contract-reviewer && .venv/bin/python -m scripts.purge_reports

Deleting is unrecoverable and the contract text goes with it, so the window has
to be stated somewhere explicit — in ``.env`` or on the command line — and
``--dry-run`` answers "how much would that take" without taking it.

Under ``REPORT_STORAGE=redis`` this exits without doing anything: those keys
carry a native TTL and expire whether or not a job ever runs.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.dependencies import get_report_repo
from app.repositories.report import PostgresReportRepository


def main(argv: list[str]) -> int:
    """Purge reports older than the retention window; print what was removed."""
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--older-than-days",
        type=float,
        default=settings.report_retention_days,
        help="retention window in days (default: REPORT_RETENTION_DAYS)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be deleted without deleting it",
    )
    args = parser.parse_args(argv[1:])

    if args.older_than_days is None:
        # Not an error: a deployment with no retention policy is a valid one,
        # and it is the deployment this defaults to.
        print(
            "no retention window set - reports are kept until their owner deletes them.\n"
            "Set REPORT_RETENTION_DAYS in .env or pass --older-than-days N to purge."
        )
        return 0
    if args.older_than_days <= 0:
        parser.error("--older-than-days must be greater than 0")

    repo = get_report_repo()
    if not isinstance(repo, PostgresReportRepository):
        print(
            f"REPORT_STORAGE={settings.report_storage}: reports already expire on their own "
            f"after {settings.retention_ttl_seconds}s, nothing to purge."
        )
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=args.older_than_days)
    if args.dry_run:
        print(
            f"would delete {repo.count_older_than(cutoff)} report(s) "
            f"created before {cutoff.isoformat()}"
        )
        return 0

    purged = repo.purge_older_than(cutoff)
    print(f"deleted {len(purged)} report(s) created before {cutoff.isoformat()}")
    for report_id in purged:
        # The ids are printed because after the commit this output is the only
        # record that those reviews existed.
        print(f"  {report_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
