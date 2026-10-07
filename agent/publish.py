"""Publishing: put the article on its own branch, made from the latest
origin/main in a separate git worktree (your working copy and its
uncommitted changes are never touched), run the test suite there, push, and
open a Pull Request for review. Nothing is merged automatically: merging the
PR is what publishes the article."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .files import write_articles
from .schema import Submission

# A branch without this file predates the blog, so the article could not render.
BLOG_MARKER = "app/templates/article.html"


class PublishError(RuntimeError):
    pass


@dataclass
class Published:
    branch: str
    compare_url: str | None
    pr_url: str | None


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise PublishError(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc


def github_repo(url: str) -> str | None:
    """'owner/name' for a GitHub remote URL (https or ssh), else None."""
    m = re.match(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?/?$", url.strip())
    return m.group(1) if m else None


def preflight(repo: Path, remote: str = "origin", base: str = "main") -> None:
    """Fail before spending money on the API if publishing cannot work."""
    _git(repo, "fetch", "--quiet", remote, base)
    if _git(repo, "cat-file", "-e", f"{remote}/{base}:{BLOG_MARKER}", check=False).returncode != 0:
        raise PublishError(
            f"{remote}/{base} does not have the blog yet ({BLOG_MARKER} is missing). "
            "Commit and push the blog and CMS changes first, then run the agent again."
        )


def snapshot_content(repo: Path, dest: Path, remote: str = "origin", base: str = "main") -> Path:
    """Extract content/ as it is on remote/base. The PR is built on that
    branch, so the agent must see (and be checked against) its articles, not
    local drafts that were never pushed."""
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", f"{remote}/{base}", "content"],
        capture_output=True,
    )
    if archive.returncode != 0:
        raise PublishError(f"could not read content/ from {remote}/{base}:\n{archive.stderr.decode()}")
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)
    return dest / "content"


def _free_branch(repo: Path, remote: str, name: str) -> str:
    branch, n = name, 2
    while (
        _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0
        or _git(repo, "ls-remote", "--exit-code", "--heads", remote, branch, check=False).returncode == 0
    ):
        branch, n = f"{name}-{n}", n + 1
    return branch


def pr_body(sub: Submission, topic: str) -> str:
    sources = "\n".join(f"- [{s.title}]({s.url}): {s.used_for}" for s in sub.sources) or "- (none)"
    claims = "\n".join(f"- [ ] {c}" for c in sub.claims_to_verify) or "- (none)"
    return f"""## New article: {sub.vi.title}

- Vietnamese: `/blog/{sub.vi.slug}/` ({len(sub.vi.body.split())} words)
- English: `/en/blog/{sub.en.slug}/` ({len(sub.en.body.split())} words)
- Target search phrase: **{sub.primary_keyword}**
- Topic given to the agent: {topic}

Written by the article agent (`python -m agent`). It passed the site's SEO audit and test suite. **Read it on the Vercel preview before merging. Merging publishes it.**

### Facts to double-check
{claims}

### Notes from the agent
{sub.reviewer_notes}

### Sources
{sources}
"""


def publish_pr(
    sub: Submission,
    repo: Path,
    topic: str,
    *,
    remote: str = "origin",
    base: str = "main",
    published: date | None = None,
    run_tests: bool = True,
    python: str = sys.executable,
) -> Published:
    repo = Path(repo)
    preflight(repo, remote, base)
    branch = _free_branch(repo, remote, f"article/{sub.vi.slug}")
    worktree = Path(tempfile.mkdtemp(prefix="article-")) / "repo"
    _git(repo, "worktree", "add", "--quiet", "-b", branch, str(worktree), f"{remote}/{base}")
    try:
        paths = write_articles(sub, worktree / "content", published or date.today())
        if run_tests:
            proc = subprocess.run(
                [python, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                cwd=worktree, capture_output=True, text=True,
            )
            if proc.returncode != 0:
                raise PublishError("The test suite fails with the new article:\n" + proc.stdout[-3000:])
        _git(worktree, "add", *[str(p.relative_to(worktree)) for p in paths])
        _git(worktree, "commit", "--quiet", "-m", f"Add article: {sub.vi.title}\n\nEnglish version: {sub.en.title}")
        _git(worktree, "push", "--quiet", "-u", remote, branch)
    except Exception:
        _git(repo, "worktree", "remove", "--force", str(worktree), check=False)
        _git(repo, "branch", "-D", branch, check=False)
        raise
    _git(repo, "worktree", "remove", "--force", str(worktree), check=False)

    gh_repo = github_repo(_git(repo, "remote", "get-url", remote).stdout)
    compare = f"https://github.com/{gh_repo}/compare/{base}...{branch}?expand=1" if gh_repo else None
    pr_url = None
    if gh_repo and shutil.which("gh"):
        proc = subprocess.run(
            ["gh", "pr", "create", "--repo", gh_repo, "--base", base, "--head", branch,
             "--title", f"New article: {sub.vi.title}", "--body", pr_body(sub, topic)],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            pr_url = proc.stdout.strip().splitlines()[-1]
    return Published(branch, compare, pr_url)
