"""scripts/check_article.py: the checks the writing agent runs before a PR."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_article import check  # noqa: E402

GEMINI_VI = "content/vi/articles/cach-su-dung-google-gemini-cho-doanh-nghiep-nho.json"


def _site_copy(tmp_path) -> Path:
    shutil.copytree(ROOT / "content", tmp_path / "content")
    return tmp_path / "content"


def test_existing_articles_pass():
    files = [str(p.relative_to(ROOT)) for p in sorted(ROOT.glob("content/*/articles/*.json"))]
    assert check(files, ROOT / "content") == []


def test_cli_prints_json():
    out = subprocess.run([sys.executable, "scripts/check_article.py", GEMINI_VI],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"problems": []}


def test_reports_audit_problems_and_dead_links(tmp_path):
    content = _site_copy(tmp_path)
    f = content / "vi" / "articles" / "bai-moi.json"
    data = json.loads((ROOT / GEMINI_VI).read_text(encoding="utf-8"))
    data.update(slug="bai-moi", translation_key="bai-moi", title="Một bài viết mới để kiểm tra")
    data["body"] += "\n\nXem [Blog](/blog/) và [bài cũ](/blog/khong-ton-tai/).\n"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    problems = check(["content/vi/articles/bai-moi.json"], content)
    assert any("same link text" in p and "Blog" in p for p in problems), problems
    assert any("/blog/khong-ton-tai/ does not exist" in p for p in problems), problems


def test_rejects_wrong_paths_and_slug_mismatch(tmp_path):
    content = _site_copy(tmp_path)
    data = json.loads((ROOT / GEMINI_VI).read_text(encoding="utf-8"))
    (content / "vi" / "articles" / "ten-file.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    problems = check(["content/vi/articles/ten-file.json", "content/vi/pages/home.json"], content)
    assert any("does not match the file name" in p for p in problems), problems
    assert any("not an article file" in p for p in problems), problems
