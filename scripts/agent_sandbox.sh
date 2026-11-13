#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
#
# Docker sandbox for the Claude Code benchmark attempt.
#
#   build                      build the agent and proxy images
#   up                         create the internal network and start the egress proxy
#   proof <log-file>           prove what the agent container can and cannot do
#   agent <work> <task> <transcript> <stderr> <model>
#                              run Claude Code once in the sandbox
#   patch <work> <out-dir>     save the agent's changes as a patch (no network)
#   proxy-log <file>           copy the proxy log
#   down                       remove containers and networks
#
# The agent container sits on an --internal Docker network, so it has no route to
# anything. The only other container on that network is a proxy that forwards CONNECT
# requests to api.anthropic.com:443 and refuses every other host and port.
set -u

RUN_ID="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-$$"
AGENT_IMAGE="bench-agent:${RUN_ID}"
PROXY_IMAGE="bench-egress:${RUN_ID}"
INTERNAL_NET="bench-internal-${RUN_ID}"
EGRESS_NET="bench-egress-${RUN_ID}"
PROXY_NAME="bench-proxy-${RUN_ID}"
PROXY_URL="http://${PROXY_NAME}:3128"
STATE_FILE="${BENCH_SANDBOX_STATE:-${RUNNER_TEMP:-/tmp}/agent-sandbox.env}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# Flags shared by every container that runs agent-controlled content.
hardening=(
    --user "$(id -u):$(id -g)"
    --read-only
    --tmpfs /tmp:rw,exec,nosuid,size=4g
    --tmpfs /home/agent:rw,exec,nosuid,size=1g
    --cap-drop ALL
    --security-opt no-new-privileges
    --pids-limit 4096
    --memory 12g
)
proxy_env=(
    -e "HTTPS_PROXY=${PROXY_URL}" -e "HTTP_PROXY=${PROXY_URL}"
    -e "https_proxy=${PROXY_URL}" -e "http_proxy=${PROXY_URL}"
    -e "NO_PROXY=" -e "no_proxy="
)

save_state() {
    printf 'AGENT_IMAGE=%s\nPROXY_IMAGE=%s\nINTERNAL_NET=%s\nEGRESS_NET=%s\nPROXY_NAME=%s\nPROXY_URL=%s\n' \
        "$AGENT_IMAGE" "$PROXY_IMAGE" "$INTERNAL_NET" "$EGRESS_NET" "$PROXY_NAME" "$PROXY_URL" > "$STATE_FILE"
}

load_state() {
    [ -f "$STATE_FILE" ] || { echo "sandbox is not built: $STATE_FILE missing" >&2; exit 2; }
    # shellcheck disable=SC1090
    . "$STATE_FILE"
    PROXY_URL="http://${PROXY_NAME}:3128"
    proxy_env=(
        -e "HTTPS_PROXY=${PROXY_URL}" -e "HTTP_PROXY=${PROXY_URL}"
        -e "https_proxy=${PROXY_URL}" -e "http_proxy=${PROXY_URL}"
        -e "NO_PROXY=" -e "no_proxy="
    )
}

cmd_build() {
    docker build --quiet -t "$AGENT_IMAGE" "$ROOT/docker/claude-agent" >/dev/null || return 1
    docker build --quiet -t "$PROXY_IMAGE" "$ROOT/docker/egress-proxy" >/dev/null || return 1
    save_state
    echo "agent image id: $(docker image inspect --format '{{.Id}}' "$AGENT_IMAGE")"
    echo "claude version: $(docker run --rm --user "$(id -u):$(id -g)" "$AGENT_IMAGE" claude --version)"
}

cmd_up() {
    load_state
    docker network create --internal "$INTERNAL_NET" >/dev/null || return 1
    docker network create "$EGRESS_NET" >/dev/null || return 1
    docker run -d --name "$PROXY_NAME" --network "$EGRESS_NET" --cap-drop ALL \
        --security-opt no-new-privileges --read-only --tmpfs /tmp:rw "$PROXY_IMAGE" >/dev/null || return 1
    docker network connect --alias "$PROXY_NAME" "$INTERNAL_NET" "$PROXY_NAME" || return 1
    for _ in $(seq 1 30); do
        if docker run --rm --network "$INTERNAL_NET" "$AGENT_IMAGE" \
            bash -c "exec 3<>/dev/tcp/${PROXY_NAME}/3128" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    echo "egress proxy did not start" >&2
    docker logs "$PROXY_NAME" >&2 || true
    return 1
}

in_agent_net() {
    docker run --rm "${hardening[@]}" --network "$INTERNAL_NET" "${proxy_env[@]}" "$@"
}

# expect <label> <fail|pass> <command...>: run in the agent container and compare.
PROOF_FAILED=0
expect() {
    local label=$1 want=$2 out code
    shift 2
    out=$(in_agent_net "$AGENT_IMAGE" "$@" 2>&1)
    code=$?
    if { [ "$want" = fail ] && [ "$code" -ne 0 ]; } || { [ "$want" = pass ] && [ "$code" -eq 0 ]; }; then
        printf 'OK    %-58s (exit %s)\n' "$label" "$code"
    else
        printf 'FAIL  %-58s expected %s, got exit %s\n      %s\n' "$label" "$want" "$code" "${out:0:300}"
        PROOF_FAILED=1
    fi
}

cmd_proof() {
    load_state
    local log=$1 work
    work=$(mktemp -d)
    {
        echo "== Network and sandbox proof, $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
        echo "Agent container: internal network, no default route; egress only via ${PROXY_NAME} (api.anthropic.com:443)."
        expect "direct github.com (no proxy) is unreachable" fail \
            curl --noproxy '*' -sS -m 10 -o /dev/null https://github.com
        expect "direct api.anthropic.com (no proxy) is unreachable" fail \
            curl --noproxy '*' -sS -m 10 -o /dev/null https://api.anthropic.com
        expect "direct IP 1.1.1.1 is unreachable" fail \
            curl --noproxy '*' -sS -m 5 -o /dev/null http://1.1.1.1
        expect "DNS for github.com does not resolve" fail getent hosts github.com
        expect "github.com through the proxy is refused" fail \
            curl -sS -m 15 -o /dev/null https://github.com
        expect "example.com through the proxy is refused" fail \
            curl -sS -m 15 -o /dev/null https://example.com
        expect "api.anthropic.com on port 8443 is refused" fail \
            curl -sS -m 15 -o /dev/null https://api.anthropic.com:8443
        expect "api.anthropic.com:443 is reachable through the proxy" pass \
            curl -sS -m 30 -o /dev/null https://api.anthropic.com/
        expect "root filesystem is read-only" fail touch /etc/bench-write-test
        expect "container is not root" pass sh -c 'test "$(id -u)" != 0'
        expect "no Linux capabilities" pass sh -c 'grep -q "^CapEff:.0000000000000000$" /proc/self/status'
        out=$(docker run --rm "${hardening[@]}" --network "$INTERNAL_NET" -v "$work":/work:rw "$AGENT_IMAGE" \
            sh -c 'touch /work/probe && echo wrote-work' 2>&1)
        case "$out" in
            *wrote-work*) printf 'OK    %-58s\n' "the work directory is writable" ;;
            *) printf 'FAIL  %-58s %s\n' "the work directory is writable" "${out:0:200}"; PROOF_FAILED=1 ;;
        esac
        # Start Claude Code with a deliberately fake token. It must get as far as asking the
        # API (through the proxy) and be refused there; the proxy log then shows every host it
        # tried to reach. A start-up failure of any other kind fails the proof.
        out=$(printf 'hello' | in_agent_net -i -e ANTHROPIC_API_KEY=probe-not-a-real-key-0000000000 \
            "$AGENT_IMAGE" timeout 120 claude -p --no-session-persistence --safe-mode \
            --strict-mcp-config --disable-slash-commands --permission-mode acceptEdits \
            --permission-prompts none --tools Bash,Read,Edit,Write,Glob,Grep \
            --allowedTools Bash,Read,Edit,Write,Glob,Grep --disallowedTools WebSearch,WebFetch \
            --output-format stream-json --verbose --model claude-opus-5-5 2>&1)
        printf '      claude printed: %s\n' "$(printf '%s' "${out:0:400}" | tr '\n' ' ')"
        case "$out" in
            *"could not start"*|*"unknown option"*|*"invalid"*"choice"*|*"did you mean"*|*bubblewrap*)
                printf 'FAIL  %-58s\n' "Claude Code starts with the invocation flags"; PROOF_FAILED=1 ;;
            *) printf 'OK    %-58s\n' "Claude Code starts with the invocation flags (fake key: API refusal expected)" ;;
        esac
        if [ "$PROOF_FAILED" -eq 0 ]; then echo "RESULT: all proofs passed"; else echo "RESULT: PROOF FAILED"; fi
    } 2>&1 | tee "$log"
    rm -rf "$work"
    # tee hides the block's status, so decide from the log.
    grep -q '^RESULT: all proofs passed$' "$log"
}

cmd_agent() {
    load_state
    local work=$1 task=$2 transcript=$3 stderr_log=$4 model=$5
    docker run --rm -i --name "bench-agent-${RUN_ID}" "${hardening[@]}" --network "$INTERNAL_NET" \
        "${proxy_env[@]}" -e ANTHROPIC_API_KEY -v "$work":/work:rw -w /work "$AGENT_IMAGE" \
        timeout -k 30 3600 claude -p --output-format stream-json --verbose --no-session-persistence \
        --safe-mode --strict-mcp-config --disable-slash-commands --permission-mode acceptEdits \
        --permission-prompts none --tools Bash,Read,Edit,Write,Glob,Grep \
        --allowedTools Bash,Read,Edit,Write,Glob,Grep --disallowedTools WebSearch,WebFetch \
        --model "$model" < "$task" > "$transcript" 2> "$stderr_log"
}

cmd_patch() {
    load_state
    local work=$1 out=$2
    docker run --rm --network none "${hardening[@]}" -v "$work":/work:rw -v "$out":/out:rw -w /work "$AGENT_IMAGE" \
        sh -c 'git -c safe.directory=/work -c core.hooksPath=/dev/null -c core.fsmonitor= add -A -- . ":(exclude,glob)build*/**" ":(exclude,glob)**/build*/**" \
            && git -c safe.directory=/work -c core.hooksPath=/dev/null -c core.fsmonitor= diff --cached --binary --no-ext-diff --no-textconv HEAD > /out/agent-fix.patch'
}

cmd_proxy_log() {
    load_state
    docker exec "$PROXY_NAME" cat /tmp/tinyproxy.log > "$1" 2>/dev/null || : > "$1"
}

cmd_down() {
    [ -f "$STATE_FILE" ] || return 0
    load_state
    docker rm -f "$PROXY_NAME" >/dev/null 2>&1 || true
    docker network rm "$INTERNAL_NET" "$EGRESS_NET" >/dev/null 2>&1 || true
    docker rmi -f "$AGENT_IMAGE" "$PROXY_IMAGE" >/dev/null 2>&1 || true
}

command_name=${1:-}
[ $# -gt 0 ] && shift
case "$command_name" in
    build) cmd_build ;;
    up) cmd_up ;;
    proof) cmd_proof "$@" ;;
    agent) cmd_agent "$@" ;;
    patch) cmd_patch "$@" ;;
    proxy-log) cmd_proxy_log "$@" ;;
    down) cmd_down ;;
    *) echo "usage: $0 build|up|proof|agent|patch|proxy-log|down" >&2; exit 2 ;;
esac
