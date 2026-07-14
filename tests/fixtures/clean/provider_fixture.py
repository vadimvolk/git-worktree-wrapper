#!/usr/bin/env python3
"""Fixture provider for ``gww clean`` tests.

Reads its mode from the ``$GWW_FIXTURE_MODE`` env var (set by the test
runner when wiring ``providers.<kind>.merged`` to point at this script)
and exits according to the chosen mode:

* ``exit0``   -> exit 0 (provider says "merged")
* ``exit1``   -> exit 1 (provider says "not merged")
* ``sleep``   -> sleep 70s so the 60s timeout fires
* ``missing`` -> a leading command that the shell cannot resolve, exiting 127

In all modes except ``exit0``, the script writes the rendered ``branch()``
value to stdout so we can confirm the template engine substituted it
correctly. The user-visible output (stdout + stderr) is what the real
``gh`` / ``glab`` / ``tea`` would have produced, so the test surface is
identical.
"""
from __future__ import annotations

import os
import sys
import time

mode = os.environ.get("GWW_FIXTURE_MODE", "exit1")

if mode == "exit0":
    print("merged")
    sys.exit(0)

if mode == "exit1":
    print("not merged")
    sys.exit(1)

if mode == "sleep":
    print("starting sleep", file=sys.stderr)
    sys.stdout.flush()
    time.sleep(70)
    sys.exit(0)

if mode == "missing":
    # Leading token does not exist on PATH -> shell exits 127.
    os.execvp("gww-fixture-missing-binary", ["gww-fixture-missing-binary"])

print(f"unknown mode: {mode}", file=sys.stderr)
sys.exit(2)