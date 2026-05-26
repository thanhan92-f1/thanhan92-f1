#!/usr/bin/env python3
"""Generate dynamic GitHub profile language and tech-stack sections.

The script scans public repositories from the personal account and managed
organizations, aggregates repository languages through the GitHub REST API,
and rewrites the generated block in README.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START = "<!-- PROFILE-METRICS:START -->"
END = "<!-- PROFILE-METRICS:END -->"
FALLBACK_LANGUAGE_BYTES = 100_000

ACCOUNTS = [
    {"type": "user", "login": "thanhan92-f1", "label": "Nguyen Thanh An"},
    {"type": "org", "login": "hitechcloud-vietnam", "label": "HiTechCloud"},
    {"type": "org", "login": "HiTechAI-VN", "label": "HiTechAI VN"},
    {
        "type": "org",
        "login": "Viet-Nam-API-Sharing-Community",
        "label": "Vietnam API Sharing Community",
    },
]

LANGUAGE_COLORS = {
    "Python": "3776AB",
    "TypeScript": "3178C6",
    "JavaScript": "F7DF1E",
    "PHP": "777BB4",
    "Shell": "4EAA25",
    "Dockerfile": "2496ED",
    "HTML": "E34F26",
    "CSS": "1572B6",
    "Go": "00ADD8",
    "C++": "00599C",
    "C#": "512BD4",
    "C": "A8B9CC",
    "Java": "ED8B00",
    "Vue": "4FC08D",
    "Svelte": "FF3E00",
    "Rust": "000000",
    "Ruby": "CC342D",
    "Jupyter Notebook": "F37626",
    "Blade": "F7523F",
    "PowerShell": "5391FE",
    "Makefile": "427819",
    "SCSS": "CC6699",
}

TECH_RULES = {
    "Python": ["Python", "FastAPI", "SDK", "Automation"],
    "TypeScript": ["TypeScript", "Node.js", "VS Code Extension", "Developer Tools"],
    "JavaScript": ["JavaScript", "Web UI", "Automation", "Cloud Dashboard"],
    "PHP": ["PHP", "Laravel", "Panel", "Backend"],
    "Shell": ["Shell", "Linux", "Provisioning", "One-click Setup"],
    "Dockerfile": ["Docker", "Container", "Deployment"],
    "Go": ["Go", "CLI", "Cloud Native"],
    "C++": ["C++", "Performance", "Systems"],
    "C#": ["C#", ".NET", "Desktop/Backend"],
    "HTML": ["HTML", "Docs", "Static UI"],
    "CSS": ["CSS", "Frontend", "UI"],
}

TOPIC_TECH = {
    "ai": "AI Engineering",
    "artificial-intelligence": "AI Engineering",
    "llm": "LLM / Local AI",
    "ollama": "Ollama / Local AI",
    "nvidia": "NVIDIA GPU",
    "dgx": "NVIDIA DGX Spark",
    "cloud": "Cloud Platform",
    "kubernetes": "Kubernetes / K3s",
    "k3s": "Kubernetes / K3s",
    "proxmox": "Proxmox",
    "docker": "Docker",
    "api": "API Integration",
    "fastapi": "FastAPI",
    "banking": "Banking API",
    "automation": "Automation",
    "devtools": "Developer Tools",
    "vscode": "VS Code Extension",
}


@dataclass(frozen=True)
class Repo:
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str
    language: str | None
    stargazers_count: int
    forks_count: int
    topics: tuple[str, ...]
    archived: bool
    fork: bool


class GitHubClient:
    def __init__(self) -> None:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "thanhan92-f1-profile-metrics",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get_json(self, url: str) -> Any:
        request = urllib.request.Request(url, headers=self.headers)
        last_error: RuntimeError | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                message = error.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"GitHub API error {error.code} for {url}: {message}")
                if error.code not in {403, 429, 500, 502, 503, 504} or attempt == 2:
                    raise last_error from error
                retry_after = error.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(min(delay, 10))
        if last_error:
            raise last_error
        raise RuntimeError(f"GitHub API request failed for {url}")

    def list_repos(self, account_type: str, login: str) -> list[Repo]:
        path = "users" if account_type == "user" else "orgs"
        repos: list[Repo] = []
        page = 1
        while True:
            repo_type = "owner" if account_type == "user" else "public"
            query = urllib.parse.urlencode(
                {
                    "type": repo_type,
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": 100,
                    "page": page,
                }
            )
            url = f"https://api.github.com/{path}/{login}/repos?{query}"
            data = self.get_json(url)
            if not data:
                break
            for item in data:
                repos.append(
                    Repo(
                        owner=item["owner"]["login"],
                        name=item["name"],
                        full_name=item["full_name"],
                        html_url=item["html_url"],
                        description=item.get("description") or "",
                        language=item.get("language"),
                        stargazers_count=item.get("stargazers_count", 0),
                        forks_count=item.get("forks_count", 0),
                        topics=tuple(item.get("topics", [])),
                        archived=bool(item.get("archived", False)),
                        fork=bool(item.get("fork", False)),
                    )
                )
            if len(data) < 100:
                break
            page += 1
        return repos

    def repo_languages(self, full_name: str) -> dict[str, int]:
        return self.get_json(f"https://api.github.com/repos/{full_name}/languages")


def shield(label: str, color: str = "0EA5E9", logo: str | None = None) -> str:
    safe_label = label.replace("-", "--").replace(" ", "%20")
    logo_part = f"&logo={logo}&logoColor=white" if logo else ""
    return f"![{label}](https://img.shields.io/badge/{safe_label}-{color}?style=for-the-badge{logo_part})"


def percentage(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(value * 100 / total, 1)


def progress_bar(pct: float) -> str:
    filled = max(1, min(20, round(pct / 5))) if pct > 0 else 0
    return "█" * filled + "░" * (20 - filled)


def repo_score(repo: Repo) -> int:
    topic_bonus = len(repo.topics) * 3
    archive_penalty = -100 if repo.archived else 0
    fork_penalty = -20 if repo.fork else 0
    return repo.stargazers_count * 6 + repo.forks_count * 3 + topic_bonus + archive_penalty + fork_penalty


def aggregate() -> tuple[dict[str, list[Repo]], Counter[str], Counter[str], list[Repo], list[str]]:
    client = GitHubClient()
    repos_by_account: dict[str, list[Repo]] = {}
    language_bytes: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    all_repos: list[Repo] = []
    failed_accounts: list[str] = []

    for account in ACCOUNTS:
        try:
            repos = client.list_repos(account["type"], account["login"])
        except RuntimeError as error:
            print(f"warning: cannot fetch repositories for {account['login']}: {error}", file=sys.stderr)
            repos_by_account[account["login"]] = []
            failed_accounts.append(account["login"])
            continue

        repos_by_account[account["login"]] = repos
        all_repos.extend(repos)
        for repo in repos:
            topics.update(repo.topics)
            try:
                language_bytes.update(client.repo_languages(repo.full_name))
            except RuntimeError as error:
                print(f"warning: cannot fetch languages for {repo.full_name}: {error}", file=sys.stderr)
                if repo.language:
                    language_bytes[repo.language] += FALLBACK_LANGUAGE_BYTES
            time.sleep(0.15)

    return repos_by_account, language_bytes, topics, all_repos, failed_accounts


def render_language_rows(language_bytes: Counter[str]) -> list[str]:
    total = sum(language_bytes.values())
    rows = ["| Language | Usage | Share |", "|---|---:|---|"]
    for language, count in language_bytes.most_common(12):
        pct = percentage(count, total)
        rows.append(f"| **{language}** | `{progress_bar(pct)}` | **{pct}%** |")
    return rows


def render_language_badges(language_bytes: Counter[str]) -> str:
    badges: list[str] = []
    logo_map = {
        "C++": "cplusplus",
        "C#": "dotnet",
        "Jupyter Notebook": "jupyter",
        "Shell": "gnubash",
        "Dockerfile": "docker",
    }
    for language, _ in language_bytes.most_common(14):
        color = LANGUAGE_COLORS.get(language, "64748B")
        logo = logo_map.get(language, language.lower().replace(" ", ""))
        logo_color = "000" if language in {"JavaScript", "Linux"} else "white"
        safe_label = language.replace("-", "--").replace(" ", "%20").replace("#", "%23").replace("+", "%2B")
        badges.append(
            f"![{language}](https://img.shields.io/badge/{safe_label}-{color}?style=for-the-badge&logo={logo}&logoColor={logo_color})"
        )
    return "\n".join(badges)


def render_account_summary(repos_by_account: dict[str, list[Repo]]) -> list[str]:
    rows = ["| Scope | Public repos scanned | Top primary languages |", "|---|---:|---|"]
    for account in ACCOUNTS:
        repos = repos_by_account.get(account["login"], [])
        primary = Counter(repo.language for repo in repos if repo.language)
        top = ", ".join(language for language, _ in primary.most_common(5)) or "N/A"
        rows.append(f"| **{account['label']}** | {len(repos)} | {top} |")
    return rows


def render_tech_stack(language_bytes: Counter[str], topics: Counter[str]) -> list[str]:
    derived: list[str] = []
    for language, _ in language_bytes.most_common(10):
        derived.extend(TECH_RULES.get(language, [language]))
    for topic, _ in topics.most_common(30):
        normalized = topic.lower()
        if normalized in TOPIC_TECH:
            derived.append(TOPIC_TECH[normalized])

    unique: list[str] = []
    seen = set()
    for item in derived:
        if item not in seen:
            unique.append(item)
            seen.add(item)

    rows = ["| Auto-detected stack | Signal |", "|---|---|"]
    categories = {
        "Languages & Backend": [
            item
            for item in unique
            if item in {"Python", "TypeScript", "JavaScript", "PHP", "Go", "Node.js", "FastAPI", "SDK", "Laravel"}
        ],
        "Cloud / DevOps / Infra": [
            item
            for item in unique
            if item in {
                "Docker",
                "Container",
                "Deployment",
                "Linux",
                "Provisioning",
                "Cloud Platform",
                "Kubernetes / K3s",
                "Proxmox",
                "NVIDIA GPU",
                "NVIDIA DGX Spark",
            }
        ],
        "AI / Automation / Tooling": [
            item
            for item in unique
            if item in {
                "AI Engineering",
                "LLM / Local AI",
                "Ollama / Local AI",
                "Automation",
                "Developer Tools",
                "VS Code Extension",
                "One-click Setup",
                "CLI",
            }
        ],
        "API / Community": [
            item
            for item in unique
            if item in {"API Integration", "Banking API", "Docs", "Static UI"}
        ],
    }
    for category, items in categories.items():
        signal = " · ".join(items[:10]) if items else "Updating from repository metadata"
        rows.append(f"| **{category}** | {signal} |")
    return rows


def render_featured_repos(repos: list[Repo]) -> list[str]:
    rows = ["| Repository | Main signal |", "|---|---|"]
    candidates = sorted(repos, key=repo_score, reverse=True)[:8]
    for repo in candidates:
        signal_parts = []
        if repo.language:
            signal_parts.append(repo.language)
        if repo.topics:
            signal_parts.append(" · ".join(repo.topics[:3]))
        if repo.stargazers_count:
            signal_parts.append(f"⭐ {repo.stargazers_count}")
        if repo.forks_count:
            signal_parts.append(f"⑂ {repo.forks_count}")
        signal = " · ".join(signal_parts) or "Recently updated"
        rows.append(f"| [`{repo.full_name}`]({repo.html_url}) | {signal} |")
    return rows


def render_block(repos_by_account: dict[str, list[Repo]], language_bytes: Counter[str], topics: Counter[str], repos: list[Repo]) -> str:
    total_repos = sum(len(items) for items in repos_by_account.values())
    total_languages = len(language_bytes)
    generated_at = os.environ.get("GITHUB_RUN_NUMBER")
    update_note = "GitHub Actions scheduled update"
    if generated_at:
        update_note += f" · run #{generated_at}"

    lines = [
        START,
        "",
        "<div align=\"center\">",
        "",
        render_language_badges(language_bytes),
        "",
        "</div>",
        "",
        f"> Auto-generated from **{total_repos} public repositories** across the personal profile and managed organizations. Languages, repository counts and inferred stack are refreshed by GitHub Actions.",
        "",
        "### Dynamic language coverage",
        "",
        *render_language_rows(language_bytes),
        "",
        "### Account & organization scan",
        "",
        *render_account_summary(repos_by_account),
        "",
        "### Auto-detected tech stack",
        "",
        *render_tech_stack(language_bytes, topics),
        "",
        "### High-signal repositories",
        "",
        *render_featured_repos(repos),
        "",
        f"<sub>Last metrics refresh: {update_note}. Detected {total_languages} languages from GitHub repository language data.</sub>",
        "",
        END,
    ]
    return "\n".join(lines)


def replace_block(readme: str, block: str) -> str:
    if START not in readme or END not in readme:
        raise RuntimeError(f"README.md must contain {START} and {END} markers")
    before = readme.split(START, 1)[0]
    after = readme.split(END, 1)[1]
    return before + block + after


def main() -> int:
    repos_by_account, language_bytes, topics, repos, failed_accounts = aggregate()
    if failed_accounts:
        print(
            "Skipped README update because repository scanning was incomplete for: "
            + ", ".join(failed_accounts),
            file=sys.stderr,
        )
        return 0
    if not repos or not language_bytes:
        print("Skipped README update because GitHub returned no repository/language data", file=sys.stderr)
        return 0

    block = render_block(repos_by_account, language_bytes, topics, repos)
    original = README.read_text(encoding="utf-8")
    updated = replace_block(original, block)
    README.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated README metrics for {sum(len(v) for v in repos_by_account.values())} repositories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
