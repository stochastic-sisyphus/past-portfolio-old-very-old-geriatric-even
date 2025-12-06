#!/usr/bin/env python3
"""Utilities for keeping the portfolio's README in sync with GitHub."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.github.com/users/{user}/repos?per_page=100&sort=pushed"
START_MARKER = "<!-- REPO-LIST:START -->"
END_MARKER = "<!-- REPO-LIST:END -->"
DEFAULT_LIMIT = 8
DEFAULT_CACHE = Path("scripts/cache/latest_repos.json")


class PortfolioUpdateError(RuntimeError):
    """Raised when the README could not be updated."""


@dataclass(slots=True)
class Repo:
    """Representation of a GitHub repository."""

    name: str
    html_url: str
    description: str
    archived: bool
    fork: bool
    pushed_at: str | None
    updated_at: str | None

    @classmethod
    def from_api(cls, payload: dict) -> "Repo":
        """Create a :class:`Repo` from a GitHub API response payload."""

        return cls(
            name=payload.get("name", ""),
            html_url=payload.get("html_url", ""),
            description=_normalise_description(payload.get("description")),
            archived=bool(payload.get("archived", False)),
            fork=bool(payload.get("fork", False)),
            pushed_at=payload.get("pushed_at"),
            updated_at=payload.get("updated_at"),
        )

    def to_json(self) -> dict:
        """Return a JSON serialisable representation."""

        data = asdict(self)
        data["description"] = self.description
        return data


def _normalise_description(description: str | None) -> str:
    if not description:
        return ""
    collapsed = " ".join(description.strip().split())
    return collapsed[:160]


def _request(url: str, token: str | None = None) -> tuple[list[dict], str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "portfolio-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request) as response:  # noqa: S310 - controlled URL
        payload = json.load(response)
        links = response.headers.get("Link", "")
    return payload, links


def fetch_repos(user: str, token: str | None = None) -> list[Repo]:
    """Fetch all public repositories for *user* sorted by activity."""

    url = API_URL.format(user=user)
    repositories: list[Repo] = []
    while url:
        batch, links = _request(url, token)
        repositories.extend(Repo.from_api(repo) for repo in batch)
        url = _parse_next_link(links)
    repositories.sort(key=lambda r: r.pushed_at or r.updated_at or "", reverse=True)
    return repositories


def _parse_next_link(header: str) -> str | None:
    for part in header.split(","):
        if 'rel="next"' in part:
            return part[part.find("<") + 1 : part.find(">")]  # noqa: E203
    return None


def filter_repos(
    repos: Sequence[Repo], *, include_forks: bool = False, include_archived: bool = False
) -> list[Repo]:
    """Filter repositories according to user preferences."""

    return [
        repo
        for repo in repos
        if (include_forks or not repo.fork) and (include_archived or not repo.archived)
    ]


def generate_markdown(repos: Iterable[Repo], limit: int = DEFAULT_LIMIT) -> str:
    """Build the Markdown bullet list for the README."""

    lines: list[str] = []
    for repo in list(repos)[:limit]:
        description = repo.description or "No description provided."
        lines.append(f"- [{repo.name}]({repo.html_url}) - {description}")
    return "\n".join(lines)


def replace_section(text: str, start: str, end: str, replacement: str) -> str:
    begin = text.find(start)
    finish = text.find(end, begin)
    if begin == -1 or finish == -1:
        raise PortfolioUpdateError("Markers not found in README.md")
    return text[: begin + len(start)] + "\n" + replacement + "\n" + text[finish:]


def load_cache(path: Path) -> list[Repo]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    return [Repo.from_api(entry) for entry in data]


def save_cache(path: Path, repos: Iterable[Repo]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump([repo.to_json() for repo in repos], file, indent=2, sort_keys=True)
        file.write("\n")


def update_readme(
    readme_path: Path,
    repos: Iterable[Repo],
    *,
    limit: int,
) -> None:
    content = readme_path.read_text(encoding="utf-8")
    markdown = generate_markdown(list(repos), limit)
    updated = replace_section(content, START_MARKER, END_MARKER, markdown)
    readme_path.write_text(updated, encoding="utf-8")


def iter_repos(
    *,
    user: str,
    token: str | None,
    include_forks: bool,
    include_archived: bool,
    cache_path: Path,
    offline: bool,
) -> Iterator[Repo]:
    repos: list[Repo] = []
    if not offline:
        try:
            repos = fetch_repos(user, token)
            logging.info("Fetched %d repositories for %s", len(repos), user)
        except (HTTPError, URLError, TimeoutError) as exc:
            logging.warning("Falling back to cached repository list: %s", exc)
    if not repos:
        repos = load_cache(cache_path)
        if not repos:
            raise PortfolioUpdateError("Unable to fetch repositories and cache is empty.")
        logging.info("Loaded %d repositories from cache", len(repos))
    else:
        save_cache(cache_path, repos)
        logging.debug("Repository cache updated at %s", cache_path)
    yield from filter_repos(repos, include_forks=include_forks, include_archived=include_archived)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default=os.environ.get("GITHUB_USER", "stochastic-sisyphus"))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN"))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--readme", type=Path, default=Path(os.environ.get("README_PATH", "README.md")))
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--include-forks", action="store_true")
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Use cache only and skip network calls")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        repos = list(
            iter_repos(
                user=args.user,
                token=args.token,
                include_forks=args.include_forks,
                include_archived=args.include_archived,
                cache_path=args.cache,
                offline=args.offline,
            )
        )
        update_readme(args.readme, repos, limit=args.limit)
    except PortfolioUpdateError as error:
        logging.error("%s", error)
        return 1
    except Exception as error:  # pragma: no cover - defensive programming
        logging.exception("Unexpected error")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
