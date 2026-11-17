# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
# Image for the benchmark attempts of both agents (Claude Code and Codex CLI): one toolchain, one set of
# ruby/unifdef, one sandbox. The C/C++ toolchain matches the
# verifier's base image so the agent builds with the same compilers the verdict uses. ruby and unifdef are
# here because CMock generates its mocks with ruby and FreeRTOS-Plus-TCP's unit-test CMake runs unifdefall:
# without them the agent could not "run the existing tests" of a Unity case while the verifier can (BENCH-20).
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5

ARG NODE_VERSION=22.23.5
ARG NODE_SHA256=cdeb8670a0c81f51b4dc4ac61919f9b1ad917b304bf8221eb939570663d240f8
ARG CLAUDE_CODE_VERSION=2.1.323
# The Codex CLI version the first ten cases were run with (cases/*/agents/codex-cli/agent.yaml).
ARG CODEX_CLI_VERSION=0.164.0
# Same versions as docker/miner-build (Ubuntu 24.04 archive); the build fails if they drift.
ARG RUBY_VERSION=3.2.3
ARG UNIFDEF_VERSION=2.12-1

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates clang cmake curl g++ gcc gdb git libclang-rt-dev make ninja-build \
        python3 ruby unifdef valgrind xz-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


RUN set -eu; \
    check() { case "$2" in "$3"*) echo "$1 $2";; *) echo "$1 is $2, expected $3" >&2; exit 1;; esac; }; \
    check ruby "$(ruby -e 'print RUBY_VERSION')" "${RUBY_VERSION}"; \
    check unifdef "$(dpkg-query -W -f='${Version}' unifdef)" "${UNIFDEF_VERSION}"; \
    command -v unifdefall >/dev/null

RUN curl -fsSL -o /tmp/node.tar.xz \
        "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && echo "${NODE_SHA256}  /tmp/node.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && npm install -g --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@openai/codex@${CODEX_CLI_VERSION}" \
    && npm cache clean --force \
    && claude --version \
    && test "$(codex --version 2>/dev/null | tail -n 1)" = "codex-cli ${CODEX_CLI_VERSION}"

# The container runs as the runner's uid with a tmpfs home; no account is needed.
# CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 needs bubblewrap, which needs user namespaces and a
# weaker container profile, so it is off; the token is protected by the secret scan instead
# (see docs/DECISIONS.md, BENCH-13).
ENV HOME=/home/agent \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=0
WORKDIR /work
