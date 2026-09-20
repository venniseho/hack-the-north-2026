import json
import re
from types import SimpleNamespace
from typing import Any, Optional

_COMMENT_LINE_RE = re.compile(r"^\[(\d+)\] (.*)$", re.MULTILINE)
_SCAMMY = ("scam", "never received", "stay away", "thieves")


class FakeLLM:
    """Stands in for BackboardClient's comment review.

    By default it flags the numbered comments in the prompt that contain scammy
    wording, the way a real reviewer would, and quotes the first two. Pass
    `reply` to send back an exact response instead, or `error` to make the call
    raise. Every call is recorded in `calls`.
    """

    def __init__(
        self,
        *,
        keywords: tuple[str, ...] = _SCAMMY,
        category: str = "scam_accusation",
        reply: Optional[str] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        self.keywords = keywords
        self.category = category
        self.reply = reply
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def send_message(self, content: str, **kwargs: Any) -> SimpleNamespace:
        self.calls.append({"content": content, **kwargs})
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            content=self.reply if self.reply is not None else self._review(content),
            status="COMPLETED",
            messages=[],
        )

    def _review(self, prompt: str) -> str:
        comments = [(int(i), text) for i, text in _COMMENT_LINE_RE.findall(prompt)]
        flagged = [
            i
            for i, text in comments
            if any(word in text.lower() for word in self.keywords)
        ]
        return json.dumps(
            {
                "flagged": [{"i": i, "category": self.category} for i in flagged],
                "summary": (
                    f"{len(flagged)} of {len(comments)} comments say the store "
                    "is a scam."
                    if flagged
                    else ""
                ),
                "quote_ids": flagged[:2],
            }
        )
