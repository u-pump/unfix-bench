# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
# HTTPS CONNECT proxy that allows api.anthropic.com:443 and nothing else.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends tinyproxy \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY allow.list /etc/tinyproxy/allow.list
USER tinyproxy
ENTRYPOINT ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
