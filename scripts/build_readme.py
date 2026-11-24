"""Rebuild the self-updating sections of the profile README.

The README holds pairs of markers such as ``<!-- projects starts -->`` and
``<!-- projects ends -->``. This script asks the GitHub REST API for the
user's latest public work and rewrites only the text between those markers,
so everything else in the README stays exactly as written by hand.

Usage: python scripts/build_readme.py [path/to/README.md]
The optional GITHUB_TOKEN (or GH_TOKEN) environment variable raises the API
rate limit; the script only reads public data, so it also works without one.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

USER = "joseantoniopastorrivera-dev"
API = "https://api.github.com"
# Repositories that never appear in the lists: the profile itself and the
# teacher's course repository, which is not my own work.
EXCLUDED = {USER, "cybersec2627"}
PROJECT_LIMIT = 8
COMMIT_REPOS = 5
COMMIT_LIMIT = 8


def fetch_json(path, token=None):
    """GET one API path and return the decoded JSON body."""
    request = urllib.request.Request(API + path)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "profile-readme-builder")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def english_part(description):
    """Keep the English half of a bilingual 'English | Español' description."""
    if not description:
        return ""
    return description.split(" | ")[0].strip()


def shorten(text, limit=90):
    """Cut long text at a word boundary and add an ellipsis."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def pick_repos(repos, limit=PROJECT_LIMIT):
    """Public, own, active repositories, most recently pushed first."""
    own = [
        repo for repo in repos
        if not repo["private"]
        and not repo["fork"]
        and not repo["archived"]
        and repo["name"] not in EXCLUDED
    ]
    own.sort(key=lambda repo: repo["pushed_at"], reverse=True)
    return own[:limit]


def format_repo(repo):
    """One Markdown bullet for a repository."""
    line = f"* [{repo['name']}]({repo['html_url']})"
    description = shorten(english_part(repo["description"]))
    if description:
        line += f" - {description}"
    details = [f"`{repo['language']}`"] if repo["language"] else []
    details.append(repo["pushed_at"][:10])
    return line + " · " + " · ".join(details)


def first_line(message):
    """The subject line of a commit message."""
    return message.strip().splitlines()[0] if message.strip() else ""


def format_commit(item):
    """One Markdown bullet for a (repository, commit) pair."""
    repo, commit = item
    subject = shorten(first_line(commit["commit"]["message"]), 80)
    subject = subject.replace("[", "\\[").replace("]", "\\]")
    date = commit["commit"]["committer"]["date"][:10]
    return f"* [{subject}]({commit['html_url']}) in **{repo}** · {date}"


def latest_commits(repos, fetch):
    """Newest commits across the most recently pushed repositories."""
    items = []
    for repo in repos[:COMMIT_REPOS]:
        commits = fetch(f"/repos/{USER}/{repo['name']}/commits?per_page=3")
        items.extend((repo["name"], commit) for commit in commits)
    items.sort(key=lambda item: item[1]["commit"]["committer"]["date"], reverse=True)
    return items[:COMMIT_LIMIT]


def replace_section(readme, marker, lines):
    """Swap the text between the start and end markers for the new lines."""
    pattern = re.compile(
        rf"(<!-- {marker} starts -->\n).*?(<!-- {marker} ends -->)", re.DOTALL
    )
    if not pattern.search(readme):
        raise ValueError(f"README is missing the '{marker}' markers")
    body = "\n".join(lines) + "\n"
    # A function as replacement keeps backslashes in the body literal.
    return pattern.sub(lambda match: match.group(1) + body + match.group(2), readme)


def build(readme, fetch):
    """Return the README with every self-updating section refreshed."""
    repos = pick_repos(fetch(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed"))
    readme = replace_section(readme, "projects", [format_repo(r) for r in repos])
    commits = latest_commits(repos, fetch)
    return replace_section(readme, "commits", [format_commit(c) for c in commits])


def main(argv):
    path = Path(argv[1] if len(argv) > 1 else "README.md")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    readme = path.read_text(encoding="utf-8")
    updated = build(readme, lambda api_path: fetch_json(api_path, token))
    if updated != readme:
        path.write_text(updated, encoding="utf-8", newline="\n")
        print(f"{path}: updated")
    else:
        print(f"{path}: already up to date")


if __name__ == "__main__":
    main(sys.argv)
