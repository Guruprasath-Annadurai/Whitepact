#!/usr/bin/env python3
"""Run leaderboard evaluations against registered models.

    python3 scripts/run_leaderboard_eval.py                       # every active model
    python3 scripts/run_leaderboard_eval.py --model gpt-4o --provider openai
    python3 scripts/run_leaderboard_eval.py --dry-run              # mock adapter, no API keys needed

Intended for cron/scheduled execution (daily or weekly) — a live run against
a real provider costs real API-call money and takes real wall-clock time
(~55 model calls per model), so it belongs on a schedule, not in the
request/response cycle of POST /api/leaderboard/run (that endpoint exists
for admin convenience against a small registry, not production scale).

Connects directly to the configured database (same RAI_DB_PATH /
RAI_DATABASE_URL the running server uses) rather than going through the
HTTP API, so it must run co-located with (or with network access to) the
production database.

Exit code is 0 only if every targeted model ran successfully; a single
model's failure is logged and skipped rather than aborting the whole run,
but is reflected in a non-zero exit code so a cron/alerting wrapper notices.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from responsibleai.dashboard.config import get_settings
from responsibleai.db import LeaderboardRepository, create_engine
from responsibleai.leaderboard.providers import ProviderNotConfiguredError, get_adapter
from responsibleai.leaderboard.runner import LeaderboardRunner


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_engine(settings.effective_db_url)
    await engine.init()
    repo = LeaderboardRepository(engine)
    runner = LeaderboardRunner()

    try:
        if args.model and args.provider:
            target = await repo.get_model(args.model, args.provider)
            if target is None:
                print(
                    f"Model {args.provider}/{args.model} is not registered. "
                    "Register it first via POST /api/leaderboard/models.",
                    file=sys.stderr,
                )
                return 1
            targets = [target]
        else:
            targets = await repo.list_models(active_only=True)

        if not targets:
            print("No active models registered — nothing to run.")
            return 0

        exit_code = 0
        for t in targets:
            adapter_name = "mock" if args.dry_run else t["adapter"]
            try:
                adapter = get_adapter(adapter_name, t["model"], settings.leaderboard_api_keys)
            except ProviderNotConfiguredError as exc:
                print(f"SKIP {t['provider']}/{t['model']}: {exc}", file=sys.stderr)
                exit_code = 1
                continue

            print(f"Running {t['provider']}/{t['model']} ({adapter_name})...")
            try:
                result = await runner.run_model(t["model"], t["provider"], adapter)
            except Exception as exc:
                # A single model's live-API failure (timeout, rate limit, transient
                # provider outage) must not abort every other model in the run.
                print(f"FAILED {t['provider']}/{t['model']}: {exc}", file=sys.stderr)
                exit_code = 1
                continue

            stored = await repo.create_run(result)
            print(f"  -> {stored['overall_score']}/100 ({stored['grade']}), run_id={stored['id']}")

        return exit_code
    finally:
        await engine.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", help="Evaluate only this model (requires --provider too).")
    parser.add_argument("--provider", help="Provider for --model.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use the offline mock adapter for every model instead of real provider "
             "APIs — no API keys required. Verifies the full pipeline (eval, scoring, "
             "persistence) end to end without spending anything.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if bool(args.model) != bool(args.provider):
        print("--model and --provider must be provided together.", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
