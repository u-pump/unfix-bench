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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Protocol

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
    """GitHub REST over urllib. The token (read-only is enough) comes from the environment only."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "bench-miner"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            hint = " (rate limit: set GITHUB_TOKEN)" if error.code in (403, 429) else ""
            raise GitHubError(f"GET {path} -> HTTP {error.code}{hint}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise GitHubError(f"GET {path} failed: {error}") from None


def check_repo(repo: str) -> str:
    if not REPO_NAME.fullmatch(repo):
        raise ValueError(f"not an owner/repo name: {repo!r}")
    return repo


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


def dedupe(items: list[dict[str, Any]], known_keys: set[str], miner_run: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One item per change: the earliest fix wins. Later ones, and keys already in ``candidates/``, are rejected."""
    kept: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    def reject(item: dict[str, Any], detail: str) -> None:
        rows.append(rejects.make(source=item["source"], project=item["project"], ref=item["ref"],
                                 fix_commit=item["fix_commit"], stage="static", reason_code="duplicate_backport",
                                 detail=detail, fix_date=item["fix_date"], miner_run=miner_run))

    for item in sorted(items, key=lambda it: (it["fix_date"], it["project"], int(it["ref"].split("/")[1]))):
        key = item["dedupe_key"] = filters.dedupe_key(item["project"], item["title"])
        if key in known_keys:
            reject(item, f"same change as an existing candidate ({key})")
        elif key in kept:
            reject(item, f"same change as {kept[key]['project']} {kept[key]['ref']} (key {key})")
        else:
            kept[key] = item
    return list(kept.values()), rows


def known_dedupe_keys(root: Path) -> set[str]:
    keys = set()
    for path in sorted(root.glob("candidates/*/meta.yaml")):
        if not path.parent.name.startswith("_"):
            keys.add(json.loads(path.read_text(encoding="utf-8"))["dedupe_key"])
    return keys


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
    accepted, duplicates = dedupe(passed, known_dedupe_keys(root), miner_run)
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
    parser.add_argument("--query", default="fix in:title")
    parser.add_argument("--max-candidates", type=int, default=None, help="keep at most this many accepted items")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if not candidates.RUN_URL.fullmatch(args.run_url):
        parser.error("--run-url must be a GitHub Actions run URL")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        parser.error("--since must be YYYY-MM-DD")
    if not re.fullmatch(r"[\w :.<>=-]*", args.query):
        parser.error("--query may contain only letters, digits and : . < > = - and spaces")
    try:
        repos = [check_repo(name.strip()) for name in args.repos.split(",") if name.strip()] or None
        refs = parse_refs(args.prs) if args.prs.strip() else None
        result = discover(HttpClient(os.environ.get("GITHUB_TOKEN") or None), source=args.source,
                          miner_run=args.run_url, root=candidates.ROOT, repos=repos, refs=refs,
                          since=args.since, max_prs=args.max_prs, query=args.query, max_accepted=args.max_candidates)
    except (GitHubError, ValueError) as error:
        print(f"discover: {error}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["stats"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
