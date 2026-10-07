"""Command line for the article-writing agent.

    .venv/bin/python -m agent "Hướng dẫn tạo Zalo OA cho cửa hàng"            # research, write, open a PR
    .venv/bin/python -m agent "..." --notes "Nhấn mạnh chi phí"              # extra instructions
    .venv/bin/python -m agent "..." --local                                  # write into content/ only, no git
    .venv/bin/python -m agent --from-run .agent-runs/2026-10-06-x.json       # publish a saved run (no API call)
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from .checks import check
from .files import write_articles
from .publish import PublishError, pr_body, preflight, publish_pr, snapshot_content
from .schema import Submission
from .writer import MODEL, AgentError, save_run, write_article

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"
RUNS = REPO / ".agent-runs"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("topic", nargs="?", help="what the article should be about (Vietnamese or English)")
    ap.add_argument("--notes", default="", help="extra instructions: angle, audience, points to cover")
    ap.add_argument("--local", action="store_true",
                    help="only write the files into content/ to preview with `flask run`; no git, no PR")
    ap.add_argument("--from-run", type=Path, help="publish a saved run from .agent-runs/ without calling the API")
    ap.add_argument("--no-tests", action="store_true", help="skip the test suite before pushing (not recommended)")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args(argv)

    if not args.from_run and not args.topic:
        ap.error("give a topic, or --from-run FILE")
    with tempfile.TemporaryDirectory() as tmp:
        if args.local:
            content = CONTENT
        else:
            # The PR is built on origin/main: research and check against its
            # articles. Preflight first, so nothing is spent if a PR can't be made.
            try:
                preflight(REPO)
                content = snapshot_content(REPO, Path(tmp))
            except PublishError as e:
                print(e)
                return 1
        return _run(args, content)


def _run(args: argparse.Namespace, content: Path) -> int:
    if args.from_run:
        saved = json.loads(args.from_run.read_text(encoding="utf-8"))
        topic, submission = saved["topic"], Submission.model_validate(saved["submission"])
        problems = check(submission, content)
        if problems:
            print("The saved article does not pass the checks:\n" + "\n".join(f"- {p}" for p in problems))
            return 1
    else:
        topic = args.topic

        import anthropic  # only needed when calling the API

        client = anthropic.Anthropic()
        print(f"Researching and writing with {args.model} (this takes a few minutes)...")
        try:
            result = write_article(
                client, topic, notes=args.notes, model=args.model, content_dir=content,
                check=lambda sub: check(sub, content),
            )
        except AgentError as e:
            print(f"Stopped: {e}")
            return 1
        except anthropic.AuthenticationError:
            print("The API key was rejected. Check ANTHROPIC_API_KEY, or run `ant auth login`.")
            return 1
        except TypeError as e:
            # Raised by the SDK on the first request when no credential is configured.
            if "authentication method" not in str(e):
                raise
            print("No Anthropic credentials found. Set ANTHROPIC_API_KEY, or run `ant auth login`.")
            return 1
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}")
            return 1
        except anthropic.APIConnectionError:
            print("Could not reach the Anthropic API. Check the internet connection.")
            return 1
        submission = result.submission
        saved_to = save_run(result, RUNS, topic)
        print(f"Article passed the checks after {result.attempts} submission(s). Saved to {saved_to}.")
        print(f"Usage: {result.usage.summary()}")

    if args.local:
        for path in write_articles(submission, CONTENT, date.today()):
            print(f"Wrote {path.relative_to(REPO)}")
        print("Preview: .venv/bin/flask --app wsgi --debug run, then open "
              f"http://127.0.0.1:5000/blog/{submission.vi.slug}/")
        return 0

    try:
        published = publish_pr(submission, REPO, topic, run_tests=not args.no_tests)
    except PublishError as e:
        print(f"Could not publish: {e}")
        return 1
    body_file = RUNS / f"{published.branch.replace('/', '-')}-pr.md"
    RUNS.mkdir(exist_ok=True)
    body_file.write_text(pr_body(submission, topic), encoding="utf-8")
    print(f"Pushed branch {published.branch}.")
    if published.pr_url:
        print(f"Pull Request: {published.pr_url}")
    elif published.compare_url:
        print(f"Open the Pull Request here: {published.compare_url}")
        print(f"(paste the description from {body_file.relative_to(REPO)})")
    print("Review the Vercel preview on the PR, then merge to publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
