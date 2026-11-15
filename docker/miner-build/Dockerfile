# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
# Build and test image for the BENCH-20 miner. It runs other people's code, so it holds no secrets and the
# miner starts it with --network none; nothing is downloaded at run time. Tools: cmake, gcc/g++, make,
# ninja, git, python3, and ruby (Unity/CMock generate code with ruby scripts).
# The base image is the same digest as docker/claude-agent. The tool versions below are the ones the Ubuntu
# 24.04 archive gave when this file was written; the build fails if they drift, so a change is a reviewed edit.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5

ARG CMAKE_VERSION=3.28.3
ARG GCC_VERSION=13.3.0
ARG RUBY_VERSION=3.2.3

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates cmake g++ gcc git make ninja-build python3 ruby \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN set -eu; \
    check() { case "$2" in "$3"*) echo "$1 $2";; *) echo "$1 is $2, expected $3" >&2; exit 1;; esac; }; \
    check cmake "$(cmake --version | sed -n '1s/^cmake version //p')" "${CMAKE_VERSION}"; \
    check gcc "$(gcc -dumpfullversion)" "${GCC_VERSION}"; \
    check ruby "$(ruby -e 'print RUBY_VERSION')" "${RUBY_VERSION}"

WORKDIR /work
