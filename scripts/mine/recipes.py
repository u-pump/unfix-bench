# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Build recipes of the source repositories: where the unit tests are built and with which options.

Each recipe copies what the project's own CI does, with the cites below (file:line at the commit named in
``EVIDENCE_AT``). Deviations from the CI are listed in ``deviations`` so a reader can judge them.
The network is never available while building, so ``BUILD_CLONE_SUBMODULES`` is always ``OFF`` and the
submodules are fetched beforehand by ``baseline.prepare``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Upstream default branch heads the cites below were read at (2026-11, via the GitHub contents API).
EVIDENCE_AT = {
    "FreeRTOS/FreeRTOS-Plus-TCP": "b86ad086e9870099bb0ac18a75dcb7f6dd508cc7",
    "FreeRTOS/coreMQTT": "b7741e33f6a4cdc53bc680b2f50cbd6a2426dcba",
    "FreeRTOS/coreHTTP": "281a624f09c83ff221bd1823e51954ca59e535b3",
    "FreeRTOS/coreJSON": "cffa492da18c890181d64462f8af63992a69d3b0",
}

CLONE_SUBMODULES_OFF = "-DBUILD_CLONE_SUBMODULES=OFF"
CLONE_OPTION = re.compile(r"-DBUILD_CLONE_SUBMODULES(?::\w+)?=")


@dataclass(frozen=True)
class Recipe:
    project: str
    cmake_dir: str                       # cmake -S <cmake_dir>
    options: tuple[str, ...] = ()        # extra -D options (BUILD_CLONE_SUBMODULES is added separately)
    generator: str | None = None         # cmake -G <generator>; None keeps the default
    ctest_exclude: str | None = None     # ctest -E <regex>
    evidence: tuple[str, ...] = ()       # file:line cites
    deviations: str = ""


RECIPES: dict[str, Recipe] = {recipe.project: recipe for recipe in (
    Recipe(
        "FreeRTOS/FreeRTOS-Plus-TCP", "test/unit-test", generator="Ninja", ctest_exclude="system",
        evidence=(
            ".github/workflows/ci.yml:76-77 (cmake --fresh -G Ninja -S test/unit-test -B ... -DSANITIZE=; ninja)",
            ".github/workflows/ci.yml:91 (ctest -E system)",
            ".github/workflows/ci.yml:32-36 (git submodule update --checkout --init --recursive; unifdef, ninja-build)",
            "test/unit-test/CMakeLists.txt:21 (SANITIZE defaults to empty), :179-224 (needs unifdefall), :278-291 (CMock in tools/CMock)",
            ".gitmodules (tools/CMock and test/FreeRTOS-Kernel, update = none)",
        ),
        deviations="uses the non-sanitizer, non-coverage build (CI lines 76-77, 91), not the ASan build or the coverage target",
    ),
    Recipe(
        "FreeRTOS/coreMQTT", "test", options=("-DCMAKE_BUILD_TYPE=Debug", "-DUNITTEST=1", "-DCMAKE_C_FLAGS=--coverage"),
        ctest_exclude="system",
        evidence=(
            ".github/workflows/ci.yml:30-35 (cmake -S test -B build/ -DCMAKE_BUILD_TYPE=Debug -DBUILD_CLONE_SUBMODULES=ON -DUNITTEST=1 ...)",
            ".github/workflows/ci.yml:42 (ctest --test-dir build -E system)",
            "test/CMakeLists.txt:18-20 (UNITTEST), :33-34 (BUILD_CLONE_SUBMODULES), :66 (CMock in test/unit-test/CMock)",
            ".gitmodules (test/unit-test/CMock, update = none; Unity is inside CMock, so the clone is recursive)",
        ),
        deviations="CMAKE_C_FLAGS is only '--coverage' (CI: '--coverage -Wall -Wextra -Wsign-compare -Werror -DLIBRARY_LOG_LEVEL=LOG_DEBUG'). "
                   "--coverage is kept because tools/cmock/create_test.cmake:161-178 links the tests with -fprofile-arcs and the real library "
                   "must be built the same way (without it the link fails, seen in a local offline build); warnings as errors and the log level are not needed for test results; Debug keeps the asserts"
    ),
    Recipe(
        "FreeRTOS/coreHTTP", "test", options=("-DCMAKE_BUILD_TYPE=Debug", "-DUNITTEST=1"), ctest_exclude="system",
        evidence=(
            ".github/workflows/ci.yml:23-28 (cmake -S test -B build/ -DCMAKE_BUILD_TYPE=Debug -DUNITTEST=1 -DCOV_ANALYSIS=1 ...)",
            ".github/workflows/ci.yml:32 (ctest --test-dir build -E system)",
            "test/CMakeLists.txt:15-17 (UNITTEST), :30-31 (BUILD_CLONE_SUBMODULES), :87 (CMock in test/unit-test/CMock)",
            ".gitmodules (test/unit-test/CMock with update = none; llhttp without it)",
        ),
        deviations="-DCOV_ANALYSIS=1 (the extra coverity warning build) and CMAKE_C_FLAGS ('--coverage -Wall -Wextra -DNDEBUG') are not passed",
    ),
    Recipe(
        "FreeRTOS/coreJSON", "test", options=("-DCMAKE_BUILD_TYPE=Debug", "-DUNITTEST=1"), ctest_exclude="system",
        evidence=(
            ".github/workflows/ci.yml:17-21 (cmake -S test -B build/ -DCMAKE_BUILD_TYPE=Debug -DBUILD_CLONE_SUBMODULES=ON ...; UNITTEST is not passed)",
            ".github/workflows/ci.yml:26 (ctest -E system)",
            "test/CMakeLists.txt:22 (Unity in test/unit-test/Unity), :25-27 (UNITTEST is set when neither COV_ANALYSIS nor UNITTEST is defined), :31-32",
            ".gitmodules (test/unit-test/Unity, update = none)",
        ),
        deviations="CI does not pass -DUNITTEST=1; the CMakeLists turns it on by default together with the coverity build, "
                   "and passing it explicitly builds only the unit tests. CMAKE_C_FLAGS ('--coverage -Wall -Wextra -Werror') is not passed",
    ),
)}


def recipe_for(project: str) -> Recipe | None:
    return RECIPES.get(project)


def cmake_options(options: tuple[str, ...]) -> tuple[str, ...]:
    """``options`` with ``-DBUILD_CLONE_SUBMODULES=OFF`` always last. A different value is an error, never silently kept."""
    if any(CLONE_OPTION.match(option) and option != CLONE_SUBMODULES_OFF for option in options):
        raise ValueError("BUILD_CLONE_SUBMODULES is always OFF: there is no network during the build")
    return (*(option for option in options if option != CLONE_SUBMODULES_OFF), CLONE_SUBMODULES_OFF)
