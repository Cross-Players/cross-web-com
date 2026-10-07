"""Article agent: file format, checks, the Claude loop (with a scripted fake
client, no API calls) and publishing (against a local bare git remote)."""

import json
import subprocess
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from agent.checks import check
from agent.files import article_json
from agent.publish import BLOG_MARKER, PublishError, github_repo, preflight, publish_pr
from agent.schema import Draft, Submission
from agent.writer import AgentError, write_article

CONTENT = Path(__file__).resolve().parent.parent / "content"


def _existing(locale, slug):
    return json.loads((CONTENT / locale / "articles" / f"{slug}.json").read_text(encoding="utf-8"))


def valid_submission(**changes) -> Submission:
    """A new article that passes every check (bodies reused from the real articles)."""
    vi = _existing("vi", "cong-cu-ai-mien-phi-cho-doanh-nghiep-nho")
    en = _existing("en", "free-ai-tools-for-small-business")
    data = {
        "translation_key": "ai-tools-for-shops",
        "primary_keyword": "công cụ AI miễn phí",
        "vi": {
            "slug": "cong-cu-ai-cho-cua-hang",
            "title": "Công cụ AI miễn phí cho cửa hàng nhỏ",
            "description": vi["description"],
            "body": vi["body"],
        },
        "en": {
            "slug": "ai-tools-for-small-shops",
            "title": "Free AI tools for small shops",
            "description": en["description"],
            "body": en["body"],
        },
        "sources": [{"url": "https://openai.com", "title": "OpenAI", "used_for": "ChatGPT plans"}],
        "claims_to_verify": ["ChatGPT Go price"],
        "reviewer_notes": "Test article.",
    }
    for path, value in changes.items():
        target = data
        *parents, key = path.split(".")
        for p in parents:
            target = target[p]
        target[key] = value
    return Submission.model_validate(data)


# ── file format ──────────────────────────────────────────────────────────

def test_article_json_matches_cms_exporter_format():
    f = CONTENT / "vi" / "articles" / "cong-cu-ai-mien-phi-cho-doanh-nghiep-nho.json"
    raw = json.loads(f.read_text(encoding="utf-8"))
    draft = Draft(slug=raw["slug"], title=raw["title"], description=raw["description"], body=raw["body"])
    assert article_json(draft, raw["translation_key"], date.fromisoformat(raw["published"])) == f.read_text(encoding="utf-8")


# ── checks ───────────────────────────────────────────────────────────────

def test_valid_article_passes_checks():
    assert check(valid_submission(), CONTENT) == []


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"vi.slug": "huong-dan-dung-chatgpt-cho-chu-doanh-nghiep"}, "already exists"),
        ({"translation_key": "chatgpt-guide"}, "translation_key 'chatgpt-guide' is already used"),
        ({"vi.description": "Quá ngắn nhưng vẫn đủ hai mươi ký tự."}, "description is"),
        ({"en.title": "A" * 70}, "title is 70 characters"),
        ({"en.body": "# Big title\n\n" + _existing("en", "free-ai-tools-for-small-business")["body"]}, "H1 line"),
        ({"vi.body": "## A\n\n## B\n\n" + "từ " * 900}, "at least 3 '## ' sections"),
        ({"en.body": _existing("en", "free-ai-tools-for-small-business")["body"].replace(
            "/en/blog/chatgpt-guide-for-small-business-owners/", "/blog/huong-dan-dung-chatgpt-cho-chu-doanh-nghiep/")},
         "points to the Vietnamese blog"),
    ],
)
def test_static_check_failures(changes, expected):
    problems = check(valid_submission(**changes), CONTENT)
    assert any(expected in p for p in problems), problems


def test_render_checks_catch_audit_and_dead_links():
    body = _existing("vi", "cong-cu-ai-mien-phi-cho-doanh-nghiep-nho")["body"]
    body += "\n\nXem thêm trên [Blog](/blog/) và [bài cũ](/blog/khong-ton-tai/).\n"
    problems = check(valid_submission(**{"vi.body": body}), CONTENT)
    assert any("same link text is used more than once" in p and "Blog" in p for p in problems), problems
    assert any("/blog/khong-ton-tai/ does not exist" in p for p in problems), problems


# ── agent loop (fake client) ─────────────────────────────────────────────

def _usage():
    return NS(input_tokens=100, output_tokens=50, cache_creation_input_tokens=0,
              cache_read_input_tokens=0, server_tool_use=NS(web_search_requests=1))


def _msg(stop, *blocks):
    return NS(stop_reason=stop, content=list(blocks), usage=_usage(), stop_details=None)


def _submit(tool_id, payload):
    return NS(type="tool_use", id=tool_id, name="submit_article", input=payload)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = NS(messages=NS(stream=self._stream))

    @contextmanager
    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        response = self.responses.pop(0)
        yield NS(get_final_message=lambda: response)


def test_loop_handles_pause_nudge_errors_and_accepts_valid_article():
    good = valid_submission().model_dump()
    search = NS(type="server_tool_use", id="srv1", name="web_search", input={"query": "chatgpt go giá"})
    client = FakeClient([
        _msg("pause_turn", search),                                 # long research: server paused
        _msg("end_turn", NS(type="text", text="Here is the article...")),  # forgot the tool
        _msg("tool_use", _submit("t1", {"vi": "not an article"})),  # schema error
        _msg("tool_use", _submit("t2", good)),                      # fails the checks once
        _msg("tool_use", _submit("t3", good)),                      # passes
    ])
    verdicts = iter([["[vi] description is 50 characters"], []])
    log = []
    result = write_article(client, "AI cho cửa hàng", content_dir=CONTENT,
                           check=lambda sub: next(verdicts), today=date(2026, 10, 6), say=log.append)

    assert result.submission.vi.slug == "cong-cu-ai-cho-cua-hang"
    assert result.attempts == 3 and result.usage.calls == 5 and result.usage.searches == 5

    # request settings for Opus 5.5
    first = client.calls[0]
    assert first["model"] == "claude-opus-5-5" and first["output_config"] == {"effort": "high"}
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in first and "tool_choice" not in first
    assert "Today is 2026-10-06" in first["messages"][0]["content"]

    # history is append-only: every request extends the previous one
    for prev, cur in zip(client.calls, client.calls[1:]):
        assert cur["messages"][: len(prev["messages"])] == prev["messages"]
    # pause_turn is resumed without adding a user message
    assert client.calls[1]["messages"][-1]["role"] == "assistant"
    # the nudge, then is_error results with the problems
    assert "submit_article" in client.calls[2]["messages"][-1]["content"]
    schema_err = client.calls[3]["messages"][-1]["content"][0]
    assert schema_err["is_error"] and schema_err["tool_use_id"] == "t1"
    check_err = client.calls[4]["messages"][-1]["content"][0]
    assert check_err["is_error"] and "description is 50 characters" in check_err["content"]
    assert any("web_search: chatgpt go giá" in line for line in log)


def test_loop_stops_on_refusal_and_on_repeated_failures():
    refused = FakeClient([_msg("refusal")])
    with pytest.raises(AgentError, match="declined"):
        write_article(refused, "x", content_dir=CONTENT, check=lambda s: [], say=lambda _: None)

    good = valid_submission().model_dump()
    failing = FakeClient([_msg("tool_use", _submit(f"t{i}", good)) for i in range(4)])
    with pytest.raises(AgentError, match="after 4 attempts"):
        write_article(failing, "x", content_dir=CONTENT, check=lambda s: ["still wrong"], say=lambda _: None)


# ── publishing (local bare remote) ───────────────────────────────────────

def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture()
def repo(tmp_path):
    """A clone whose origin/main has the blog, like the real repo will."""
    seed = tmp_path / "seed"
    (seed / "app" / "templates").mkdir(parents=True)
    (seed / BLOG_MARKER).write_text("article template\n")
    (seed / "content" / "vi" / "articles").mkdir(parents=True)
    (seed / "content" / "vi" / "articles" / ".keep").write_text("")
    _git(seed.parent, "init", "-q", "-b", "main", str(seed))
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    remote = tmp_path / "remote.git"
    _git(tmp_path, "clone", "-q", "--bare", str(seed), str(remote))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _git(work, "config", "user.name", "Agent Test")
    _git(work, "config", "user.email", "agent@test")
    (work / "uncommitted.txt").write_text("the owner's work in progress\n")
    return work, remote


def test_publish_pushes_branch_with_only_the_article_files(repo):
    work, remote = repo
    sub = valid_submission()
    published = publish_pr(sub, work, "topic", run_tests=False, published=date(2026, 10, 7))

    assert published.branch == "article/cong-cu-ai-cho-cua-hang"
    assert published.compare_url is None and published.pr_url is None  # not a GitHub remote
    files = _git(remote, "show", "--name-only", "--format=", published.branch).split()
    assert files == ["content/en/articles/ai-tools-for-small-shops.json",
                     "content/vi/articles/cong-cu-ai-cho-cua-hang.json"]
    data = json.loads(_git(remote, "show", f"{published.branch}:content/vi/articles/cong-cu-ai-cho-cua-hang.json"))
    assert data["published"] == "2026-10-07" and data["translation_key"] == "ai-tools-for-shops"
    # the owner's working copy is untouched and the temporary worktree is gone
    assert _git(work, "branch", "--show-current").strip() == "main"
    assert (work / "uncommitted.txt").exists()
    assert len(_git(work, "worktree", "list").splitlines()) == 1

    # a second article with the same slug gets a fresh branch name
    assert publish_pr(sub, work, "topic", run_tests=False).branch == "article/cong-cu-ai-cho-cua-hang-2"


def test_preflight_refuses_a_remote_without_the_blog(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "README.md").write_text("old site\n")
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(seed), str(work))
    with pytest.raises(PublishError, match="does not have the blog yet"):
        preflight(work)


def test_github_repo_from_remote_url():
    assert github_repo("https://github.com/Cross-Players/cross-web-com.git") == "Cross-Players/cross-web-com"
    assert github_repo("git@github.com:Cross-Players/cross-web-com.git\n") == "Cross-Players/cross-web-com"
    assert github_repo("/tmp/remote.git") is None


def test_local_preview_then_publish_saved_run(tmp_path, monkeypatch, capsys):
    """`--local` writes the article into content/; publishing that saved run
    afterwards must be checked against origin/main (which lacks it), not
    against the local copy, or it would fail with "slug already exists"."""
    import shutil

    import agent.__main__ as cli
    from agent.files import write_articles

    seed = tmp_path / "seed"
    shutil.copytree(CONTENT, seed / "content")
    (seed / "app" / "templates").mkdir(parents=True)
    (seed / BLOG_MARKER).write_text("article template\n")
    _git(tmp_path, "init", "-q", "-b", "main", str(seed))
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    remote = tmp_path / "remote.git"
    _git(tmp_path, "clone", "-q", "--bare", str(seed), str(remote))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(remote), str(work))
    _git(work, "config", "user.name", "Agent Test")
    _git(work, "config", "user.email", "agent@test")
    monkeypatch.setattr(cli, "REPO", work)
    monkeypatch.setattr(cli, "CONTENT", work / "content")
    monkeypatch.setattr(cli, "RUNS", work / ".agent-runs")

    sub = valid_submission()
    write_articles(sub, work / "content", date(2026, 10, 7))  # what --local did
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"topic": "AI cho cửa hàng", "submission": sub.model_dump()}, ensure_ascii=False))

    assert cli.main(["--from-run", str(run), "--no-tests"]) == 0, capsys.readouterr().out
    assert "Pushed branch article/cong-cu-ai-cho-cua-hang" in capsys.readouterr().out
    assert _git(remote, "branch", "--list", "article/*").strip() == "article/cong-cu-ai-cho-cua-hang"
