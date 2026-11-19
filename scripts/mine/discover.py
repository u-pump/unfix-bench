# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Discovery on GitHub: merged pull requests -> static filters -> deduplicated candidates.

Reads only (REST, no clone, no build). The transport is injected, so tests run on recorded responses.
The result of ``discover`` is plain data: accepted items for the baseline stage and rejection rows for the
log. Nothing is written to ``candidates/`` here (the job that discovers has no write access).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Protocol

import candidates
from mine import filters, rejects

API = "https://api.github.com"
REPO_NAME = re.compile(r"[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*")
PR_REF = re.compile(r"([A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*)#(\d+)")
PER_PAGE = 100
MAX_FILES = 3000  # GitHub lists at most 3000 files of a pull request

# Repositories each source searches. All FreeRTOS repositories are one family for the cap.
SOURCE_REPOS: dict[str, tuple[str, ...]] = {
    "freertos": ("FreeRTOS/FreeRTOS-Plus-TCP", "FreeRTOS/coreMQTT", "FreeRTOS/coreHTTP",
                 "FreeRTOS/coreJSON", "FreeRTOS/corePKCS11", "FreeRTOS/FreeRTOS-Kernel"),
}


class GitHubError(RuntimeError):
    pass


class Client(Protocol):
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any: ...


class HttpClient:
    """GitHub REST over urllib. The token (read-only is enough) comes from the environment only.

    A rate-limited answer (primary limit with ``x-ratelimit-remaining: 0``, or a ``retry-after`` of the secondary
    limit) is waited out and the request is repeated, so a long discovery does not stop on the hourly limit. The
    wait comes from the response headers; if all waits of one client would pass ``max_wait`` seconds, it gives up.
    """

    MAX_RETRIES = 4
    SECONDARY_WAIT = 60  # seconds, when a secondary limit names no retry-after

    def __init__(self, token: str | None = None, *, max_wait: float = 3600.0,
                 sleep: Callable[[float], None] = time.sleep, now: Callable[[], float] = time.time,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self.token = token
        self.max_wait = max_wait
        self.waited = 0.0
        self._sleep, self._now, self._open = sleep, now, opener

    def _wait_for(self, error: urllib.error.HTTPError) -> float | None:
        """Seconds to wait when ``error`` is a rate limit, else ``None``."""
        if error.code not in (403, 429):
            return None
        headers = error.headers or {}
        retry_after, remaining, reset = headers.get("retry-after"), headers.get("x-ratelimit-remaining"), headers.get("x-ratelimit-reset")
        try:
            if retry_after is not None:
                return max(float(retry_after), 1.0) + 1.0
            if remaining == "0" and reset is not None:
                return max(float(reset) - self._now(), 0.0) + 1.0
        except ValueError:
            return None
        try:
            body = error.read().decode("utf-8", "replace").lower()
        except (OSError, ValueError):
            body = ""
        return float(self.SECONDARY_WAIT) if "rate limit" in body else None

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "bench-miner"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                with self._open(urllib.request.Request(url, headers=headers), timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                wait = self._wait_for(error)
                if wait is None:
                    hint = " (rate limit: set GITHUB_TOKEN)" if error.code in (403, 429) else ""
                    raise GitHubError(f"GET {path} -> HTTP {error.code}{hint}") from None
                if attempt == self.MAX_RETRIES or self.waited + wait > self.max_wait:
                    raise GitHubError(f"GET {path} -> HTTP {error.code}: rate limit, would wait {wait:.0f} s "
                                      f"(already waited {self.waited:.0f} of {self.max_wait:.0f} s)") from None
                print(f"discover: rate limit on GET {path}; waiting {wait:.0f} s", file=sys.stderr, flush=True)
                self._sleep(wait)
                self.waited += wait
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                raise GitHubError(f"GET {path} failed: {error}") from None
        raise GitHubError(f"GET {path} failed")  # not reached


def check_repo(repo: str) -> str:
    if not REPO_NAME.fullmatch(repo):
        raise ValueError(f"not an owner/repo name: {repo!r}")
    return repo


QUERY_WORD = re.compile(r"-?[A-Za-z0-9][\w.-]*")
QUERY_QUALIFIER = re.compile(r"in:(?:title|body)|label:[\w.-]+")
QUERY_OPERATORS = frozenset({"OR", "AND", "NOT"})
MAX_QUERY = 200


def check_query(query: str) -> str:
    """Search words for the title filter. Only plain words, ``OR``/``AND``/``NOT``, ``in:title|body`` and
    ``label:x`` are allowed: a ``repo:``, ``org:`` or ``is:`` qualifier would move the search to other pull requests."""
    if len(query) > MAX_QUERY:
        raise ValueError(f"the query is longer than {MAX_QUERY} characters")
    for token in query.split():
        if not (token in QUERY_OPERATORS or QUERY_QUALIFIER.fullmatch(token) or QUERY_WORD.fullmatch(token)):
            raise ValueError(f"not allowed in a query: {token!r}")
    return query


def check_repos(source: str, repos: list[str]) -> list[str]:
    """Repositories named by the owner must belong to the source."""
    allowed = SOURCE_REPOS.get(source, ())
    for repo in repos:
        if check_repo(repo) not in allowed:
            raise ValueError(f"{repo} is not a repository of source {source!r} ({', '.join(allowed)})")
    return repos


def paged(client: Client, path: str, params: dict[str, Any], limit: int, key: str | None = None) -> list[Any]:
    """Up to ``limit`` items over pages of 100; ``key`` names the list inside a search response."""
    found: list[Any] = []
    page = 1
    while len(found) < limit:
        data = client.get(path, {**params, "per_page": PER_PAGE, "page": page})
        batch = data[key] if key else data
        found.extend(batch)
        if len(batch) < PER_PAGE:
            break
        page += 1
    return found[:limit]


def search_merged(client: Client, repo: str, since: str, limit: int, query: str = "fix in:title") -> list[int]:
    """Numbers of merged pull requests of ``repo`` since a date, newest first."""
    q = f"repo:{check_repo(repo)} is:pr is:merged merged:>={since} {query}".strip()
    items = paged(client, "/search/issues", {"q": q, "sort": "created", "order": "desc"}, limit, key="items")
    return [int(item["number"]) for item in items]


def parse_refs(text: str) -> list[tuple[str, int]]:
    """``owner/repo#N`` references from a comma or space separated list."""
    refs = []
    for token in re.split(r"[,\s]+", text.strip()):
        if not token:
            continue
        match = PR_REF.fullmatch(token)
        if not match:
            raise ValueError(f"not an owner/repo#N reference: {token!r}")
        refs.append((match.group(1), int(match.group(2))))
    return refs


def fetch_item(client: Client, source: str, repo: str, number: int, repo_info: dict[str, Any]) -> dict[str, Any] | None:
    """One pull request as the item ``filters.static_check`` reads, or ``None`` when it was never merged.

    The list of files is fetched last, and not at all for a backport (rejected without it).
    """
    pull = client.get(f"/repos/{repo}/pulls/{number}")
    merged_at = pull.get("merged_at")
    sha = pull.get("merge_commit_sha")
    if not merged_at or not sha:
        return None
    item: dict[str, Any] = {
        "source": source, "project": repo, "ref": f"pull/{number}", "fix_commit": sha,
        "title": pull.get("title") or "", "body": pull.get("body") or "",
        "labels": [label["name"] for label in pull.get("labels", [])],
        "base_ref": pull["base"]["ref"], "default_branch": repo_info.get("default_branch") or "",
        "spdx": (repo_info.get("license") or {}).get("spdx_id"),
        "fix_date": merged_at[:10], "files": [],
        "url": pull.get("html_url") or f"https://github.com/{repo}/pull/{number}",
    }
    if not filters.is_backport(item["title"], item["labels"], item["base_ref"], item["default_branch"]):
        files = paged(client, f"/repos/{repo}/pulls/{number}/files", {}, MAX_FILES)
        item["files"] = [entry["filename"] for entry in files]
    return item


def dedupe(items: list[dict[str, Any]], known_keys: dict[str, str] | set[str], miner_run: str,
           known_ids: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One item per change: the earliest fix wins. Later ones, and keys or case ids already in
    ``candidates/`` or ``cases/``, are rejected."""
    kept: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    known_ids = known_ids or {}

    def reject(item: dict[str, Any], detail: str) -> None:
        rows.append(rejects.make(source=item["source"], project=item["project"], ref=item["ref"],
                                 fix_commit=item["fix_commit"], stage="static", reason_code="duplicate_backport",
                                 detail=detail, fix_date=item["fix_date"], miner_run=miner_run))

    for item in sorted(items, key=lambda it: (it["fix_date"], it["project"], int(it["ref"].split("/")[1]))):
        key = item["dedupe_key"] = filters.dedupe_key(item["project"], item["title"])
        name = candidates.case_id(item["project"], int(item["ref"].split("/")[1]))
        if key in known_keys:
            where = known_keys[key] if isinstance(known_keys, dict) else "an existing candidate"
            reject(item, f"same change as {where} ({key})")
        elif name in known_ids:
            reject(item, f"already exists as {known_ids[name]} (id {name})")
        elif key in kept:
            reject(item, f"same change as {kept[key]['project']} {kept[key]['ref']} (key {key})")
        else:
            kept[key] = item
    return list(kept.values()), rows


def discover(client: Client, *, source: str, miner_run: str, root: Path, repos: list[str] | None = None,
             refs: list[tuple[str, int]] | None = None, since: str = "2025-01-01", max_prs: int = 50,
             query: str = "fix in:title", max_accepted: int | None = None) -> dict[str, Any]:
    """Discovery for one source: ``{"accepted", "rejected", "skipped", "stats", ...}``.

    ``refs`` (an explicit list) replaces the search; otherwise up to ``max_prs`` merged pull requests per repository.
    ``max_accepted`` keeps only the first N accepted items (the rest are counted in ``stats["deferred"]``, not rejected).
    """
    if source not in candidates.SOURCES:
        raise ValueError(f"unknown source {source!r}")
    known: list[tuple[str, int]] = []
    if refs is None:
        names = repos if repos is not None else list(SOURCE_REPOS.get(source, ()))
        if not names:
            raise ValueError(f"source {source!r} has no repositories; pass repos or refs")
        refs = [(repo, number) for repo in names for number in search_merged(client, repo, since, max_prs, query)]
        # Candidates the log already rejected for a reason about the candidate are not looked at again. Build-stage
        # rejections are about the recipe and are not final, so a newer miner version judges those again.
        final = rejects.final_refs(root, source)
        known = [(repo, number) for repo, number in refs if (repo, f"pull/{number}") in final]
        refs = [pair for pair in refs if pair not in known]
    infos: dict[str, dict[str, Any]] = {}
    passed: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for repo, number in refs:
        if repo not in infos:
            infos[repo] = client.get(f"/repos/{check_repo(repo)}")
        item = fetch_item(client, source, repo, number, infos[repo])
        if item is None:
            skipped.append(f"{repo}#{number}: not merged")
            continue
        row = filters.static_check(item, miner_run)
        if row is not None:
            rows.append(row)
        else:
            passed.append(item)
    known_keys, known_ids = candidates.existing_changes(root)
    accepted, duplicates = dedupe(passed, known_keys, miner_run, known_ids)
    rows.extend(duplicates)
    deferred = 0
    if max_accepted is not None and len(accepted) > max_accepted:
        deferred = len(accepted) - max_accepted
        accepted = accepted[:max_accepted]
    return {"source": source, "miner_run": miner_run, "accepted": accepted, "rejected": rows, "skipped": skipped,
            "stats": {"looked_at": len(refs), "accepted": len(accepted), "rejected": rejects.summary(rows),
                      "skipped": len(skipped), "deferred": deferred, "already_rejected": len(known)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover candidate fixes on GitHub (read-only).")
    parser.add_argument("--source", required=True, choices=candidates.SOURCES)
    parser.add_argument("--run-url", required=True, help="the Actions run URL, recorded in rejection rows")
    parser.add_argument("--repos", default="", help="comma separated owner/repo (default: the source's repositories)")
    parser.add_argument("--prs", default="", help="explicit owner/repo#N list instead of a search")
    parser.add_argument("--since", default="2025-01-01", help="merged on or after YYYY-MM-DD")
    parser.add_argument("--max-prs", type=int, default=50, help="pull requests looked at per repository")
    parser.add_argument("--query", default="fix in:title", help="title words; empty means every merged pull request")
    parser.add_argument("--max-candidates", type=int, default=None, help="keep at most this many accepted items")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if not candidates.RUN_URL.fullmatch(args.run_url):
        parser.error("--run-url must be a GitHub Actions run URL")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        parser.error("--since must be YYYY-MM-DD")
    if not 1 <= args.max_prs <= 1000:
        parser.error("--max-prs must be from 1 to 1000 (GitHub search returns at most 1000 results)")
    try:
        check_query(args.query)
    except ValueError as error:
        parser.error(str(error))
    try:
        repos = check_repos(args.source, [name.strip() for name in args.repos.split(",") if name.strip()]) or None
        refs = parse_refs(args.prs) if args.prs.strip() else None
        result = discover(HttpClient(os.environ.get("GITHUB_TOKEN") or None), source=args.source,
                          miner_run=args.run_url, root=candidates.ROOT, repos=repos, refs=refs,
                          since=args.since, max_prs=args.max_prs, query=args.query, max_accepted=args.max_candidates)
    except (GitHubError, ValueError) as error:
        print(f"discover: {error}", file=sys.stderr)
        return 1
    print(f"discover: repos={','.join(repos or SOURCE_REPOS[args.source])} query={args.query!r} since={args.since} "
          f"max_prs={args.max_prs}", file=sys.stderr)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["stats"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
