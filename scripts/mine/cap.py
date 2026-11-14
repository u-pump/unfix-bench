# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The per-project cap: no project, and no organisation family, gives more than 30% of the 100 cases."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

TOTAL = 100
LIMIT = 30  # 30% of TOTAL, always counted from 100, not from the cases found so far

# Repositories that count as one family. Everything else is its own project (owner/repo).
FAMILIES: tuple[tuple[str, str], ...] = (
    (r"github\.com/FreeRTOS/", "freertos"),
    (r"github\.com/zephyrproject-rtos/", "zephyr"),
    (r"github\.com/apache/nuttx(?:-apps)?(?:\.git)?$", "nuttx"),
    (r"github\.com/Mbed-TLS/|github\.com/ARMmbed/mbedtls", "mbedtls"),
)
REPO = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def family(repo_url: str) -> str:
    """The family a repository counts toward, e.g. every FreeRTOS repository is ``freertos``."""
    for pattern, name in FAMILIES:
        if re.search(pattern, repo_url, re.IGNORECASE):
            return name
    match = REPO.search(repo_url)
    if not match:
        raise ValueError(f"not a GitHub repository URL: {repo_url!r}")
    return f"{match.group(1)}/{match.group(2)}".lower()


def counts(root: Path) -> Counter[str]:
    """Cases already published plus candidates already accepted, by family."""
    found: Counter[str] = Counter()
    for pattern in ("cases/*/case.yaml", "candidates/*/case.yaml"):
        for path in sorted(root.glob(pattern)):
            if path.parent.name.startswith("_"):
                continue
            found[family(json.loads(path.read_text(encoding="utf-8"))["repo"])] += 1
    return found


def exceeds(current: Counter[str], repo_url: str, limit: int = LIMIT) -> bool:
    """True when taking one more case from this repository would pass the cap."""
    return current[family(repo_url)] + 1 > limit


def shares(current: Counter[str]) -> dict[str, float]:
    """Each family's share of the 100, in percent."""
    return {name: round(100 * number / TOTAL, 1) for name, number in sorted(current.items())}
