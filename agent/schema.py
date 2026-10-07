"""The ``submit_article`` tool Claude calls when its draft is ready, and the
pydantic models that validate what it sends (with eager input streaming the
API does not validate tool input, so we do)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=SLUG_PATTERN, max_length=80)
    title: str = Field(min_length=10, max_length=120)
    description: str = Field(min_length=20, max_length=300)
    body: str = Field(min_length=200)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    used_for: str


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation_key: str = Field(pattern=SLUG_PATTERN, max_length=80)
    primary_keyword: str
    vi: Draft
    en: Draft
    sources: list[Source]
    claims_to_verify: list[str]
    reviewer_notes: str

    def drafts(self) -> dict[str, Draft]:
        return {"vi": self.vi, "en": self.en}


def _draft_schema(lang: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["slug", "title", "description", "body"],
        "properties": {
            "slug": {
                "type": "string",
                "description": f"URL slug of the {lang} version: lowercase ASCII words joined by hyphens.",
            },
            "title": {"type": "string", "description": f"{lang} headline (the page's H1)."},
            "description": {"type": "string", "description": f"{lang} meta description, 120-155 characters."},
            "body": {"type": "string", "description": f"{lang} article body in Markdown, starting with the intro paragraph (no H1)."},
        },
    }


SUBMIT_TOOL = {
    "name": "submit_article",
    "description": (
        "Submit the finished article (Vietnamese + English) for automatic checks. "
        "The site renders both versions and runs its SEO audit. If anything fails you "
        "get the list of problems back: fix them and call this tool again with the full "
        "corrected article. Call it only when the article is complete."
    ),
    "strict": True,
    "eager_input_streaming": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "translation_key", "primary_keyword", "vi", "en",
            "sources", "claims_to_verify", "reviewer_notes",
        ],
        "properties": {
            "translation_key": {
                "type": "string",
                "description": "Short English slug shared by both versions, e.g. 'zalo-oa-guide'.",
            },
            "primary_keyword": {
                "type": "string",
                "description": "The Vietnamese search phrase the article targets.",
            },
            "vi": _draft_schema("Vietnamese"),
            "en": _draft_schema("English"),
            "sources": {
                "type": "array",
                "description": "Every web page a fact in the article relies on.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["url", "title", "used_for"],
                    "properties": {
                        "url": {"type": "string"},
                        "title": {"type": "string"},
                        "used_for": {"type": "string", "description": "Which claim this source supports."},
                    },
                },
            },
            "claims_to_verify": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Facts a human reviewer should double-check before publishing "
                "(prices, limits, availability, legal points, anything where sources disagreed).",
            },
            "reviewer_notes": {
                "type": "string",
                "description": "Short note to the reviewer: angle chosen, what was left out and why.",
            },
        },
    },
}
