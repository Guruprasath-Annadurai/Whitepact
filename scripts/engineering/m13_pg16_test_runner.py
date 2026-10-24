# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Run isolated qualification with explicit PostgreSQL 16; never silently fall back.

Set WHITEPACT_TEST_PG_ADMIN_URL to a disposable administrator target. Default
pytest coverage remains enabled. --diagnostic-no-coverage is a separately labeled
diagnostic run and cannot substitute for full coverage or hosted qualification.
"""

import argparse
import asyncio
import os
import sys


async def verify_target(url: str) -> int:
    import asyncpg

    connection = await asyncpg.connect(url, timeout=5)
    try:
        version = int(await connection.fetchval("SHOW server_version_num"))
        if not 160000 <= version < 170000:
            raise RuntimeError("Qualification requires PostgreSQL 16; no fallback permitted")
        return version
    finally:
        await connection.close()


def pytest_arguments(arguments: list[str], diagnostic: bool) -> list[str]:
    if not arguments:
        raise ValueError("Explicit test paths are required")
    command = [sys.executable, "-m", "pytest"]
    if diagnostic:
        command.extend(["-o", "addopts=", "--no-cov"])
    return command + arguments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic-no-coverage", action="store_true")
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    target = os.environ.get("WHITEPACT_TEST_PG_ADMIN_URL", "")
    if not target:
        parser.error("Explicit disposable WHITEPACT_TEST_PG_ADMIN_URL is required")
    try:
        version = asyncio.run(verify_target(target))
    except Exception as error:
        # DSNs and driver exception messages can contain credentials.
        raise SystemExit(
            f"PostgreSQL qualification preflight refused: {type(error).__name__}"
        ) from None
    arguments = options.tests
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    command = pytest_arguments(arguments, options.diagnostic_no_coverage)
    print(
        f"PostgreSQL {version}; mode="
        + ("DIAGNOSTIC_NO_COVERAGE" if options.diagnostic_no_coverage else "REPOSITORY_COVERAGE"),
        flush=True,
    )
    # A real module entry point is mandatory for multiprocessing spawn.
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
