from ...agent.tools.instagram import TAG_WINDOW_DAYS, InstagramFindings
from ...agent.tools.instagram_comments import DUPLICATE_MIN_AUTHORS
from ..types import ScoreStatus, ScoringFinding, SourceScore

SOURCE_ID = "instagram-tags"
LABEL = "Instagram Tags"
COMMENTS_SOURCE_ID = "instagram-comments"
COMMENTS_LABEL = "Instagram Comments"

_MAX_QUOTE_CHARS = 120
_SAMPLE_COUNT = 3


def _quote(text: str, limit: int = _MAX_QUOTE_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def score_instagram(findings: InstagramFindings) -> SourceScore:
    """Convert Instagram research into a source score.

    Anything we couldn't judge (no link, private, tiny account) is
    INSUFFICIENT_DATA rather than a clean bill of health, matching Reddit.
    """
    metadata = {
        "handle": findings.handle,
        "followers": findings.followers,
        "website_match": findings.website_match,
    }

    error = findings.error or findings.tags_error
    if error:
        return SourceScore(
            id=SOURCE_ID,
            label=LABEL,
            status=ScoreStatus.ERROR,
            risk_score=None,
            metadata={**metadata, "error": error},
        )

    if findings.risk_score is None:
        return SourceScore(
            id=SOURCE_ID,
            label=LABEL,
            status=ScoreStatus.INSUFFICIENT_DATA,
            risk_score=None,
            metadata={**metadata, "reason": findings.skip_reason},
        )

    handle, followers = findings.handle, findings.followers or 0
    taggers, expected = findings.recent_taggers, findings.expected_taggers or 0
    finding_metadata = {
        "url": f"https://www.instagram.com/{handle}/",
        "handle": handle,
        "followers": followers,
        "recent_taggers": taggers,
        "expected_taggers": expected,
        "window_days": TAG_WINDOW_DAYS,
        "sample_tag_urls": [tag.url for tag in findings.tags[:3] if tag.url],
    }
    risk = float(findings.risk_score)

    if taggers == 0:
        finding = ScoringFinding(
            rule_id="INSTAGRAM_NO_TAGS",
            title="No one is tagging this store on Instagram",
            explanation=(
                f"@{handle} has {followers:,} followers, but no other account "
                f"tagged it in the last {TAG_WINDOW_DAYS} days."
            ),
            impact=risk,
            metadata=finding_metadata,
        )
    elif taggers < expected:
        finding = ScoringFinding(
            rule_id="INSTAGRAM_FEW_TAGS",
            title="Few Instagram tags for the account's size",
            explanation=(
                f"Only {taggers} account(s) tagged @{handle} in the last "
                f"{TAG_WINDOW_DAYS} days; about {expected} would be expected for "
                f"{followers:,} followers."
            ),
            impact=risk,
            metadata=finding_metadata,
        )
    else:
        finding = ScoringFinding(
            rule_id="INSTAGRAM_ORGANIC_TAGS",
            title="Other accounts regularly tag this store",
            explanation=(
                f"{taggers} distinct account(s) tagged @{handle} in the last "
                f"{TAG_WINDOW_DAYS} days."
            ),
            impact=0.0,
            metadata=finding_metadata,
        )

    return SourceScore(
        id=SOURCE_ID,
        label=LABEL,
        status=ScoreStatus.AVAILABLE,
        risk_score=risk,
        findings=(finding,),
        metadata=metadata,
    )


def score_instagram_comments(findings: InstagramFindings) -> SourceScore:
    """Convert the comment analysis into a source score.

    As with tags, a store we couldn't judge (no link, private, too few
    comments) is INSUFFICIENT_DATA rather than a clean bill of health.
    """
    comments = findings.comments
    metadata = {"handle": findings.handle, "comments_analyzed": comments.analyzed}

    error = findings.error or comments.error
    if error:
        return SourceScore(
            id=COMMENTS_SOURCE_ID,
            label=COMMENTS_LABEL,
            status=ScoreStatus.ERROR,
            risk_score=None,
            metadata={**metadata, "error": error},
        )

    if comments.risk_score is None:
        return SourceScore(
            id=COMMENTS_SOURCE_ID,
            label=COMMENTS_LABEL,
            status=ScoreStatus.INSUFFICIENT_DATA,
            risk_score=None,
            metadata={**metadata, "reason": comments.skip_reason},
        )

    handle, analyzed = findings.handle, comments.analyzed
    profile_url = f"https://www.instagram.com/{handle}/"
    found: list[ScoringFinding] = []

    if comments.complaint_risk > 0:
        complaints = comments.complaints
        found.append(
            ScoringFinding(
                rule_id="INSTAGRAM_COMPLAINT_COMMENTS",
                title="Customers are complaining in the comments",
                explanation=(
                    f"{len(complaints)} comments on recent posts by"
                    f"@{handle} report problems,"
                    f"e.g. “{_quote(complaints[0].text)}”"
                ),
                impact=float(comments.complaint_risk),
                metadata={
                    "url": profile_url,
                    "handle": handle,
                    "complaints": len(complaints),
                    "comments_analyzed": analyzed,
                    "samples": [
                        {"text": _quote(c.text, 300), "post_url": c.post_url}
                        for c in complaints[:_SAMPLE_COUNT]
                    ],
                },
            )
        )

    if comments.duplicate_risk > 0:
        found.append(
            ScoringFinding(
                rule_id="INSTAGRAM_DUPLICATE_COMMENTS",
                title="Identical comments from multiple accounts",
                explanation=(
                    f"{comments.duplicate_comments} of {analyzed} comments on "
                    f"@{handle}'s posts repeat text posted by "
                    f"{DUPLICATE_MIN_AUTHORS}+ different accounts, which can "
                    "indicate manufactured engagement."
                ),
                impact=float(comments.duplicate_risk),
                metadata={
                    "url": profile_url,
                    "handle": handle,
                    "duplicate_comments": comments.duplicate_comments,
                    "comments_analyzed": analyzed,
                },
            )
        )

    if not found:
        found.append(
            ScoringFinding(
                rule_id="INSTAGRAM_CLEAN_COMMENTS",
                title="Comments look organic",
                explanation=(
                    f"No pattern of complaints or copy-pasted comments across "
                    f"{analyzed} comments on @{handle}'s posts."
                ),
                impact=0.0,
                metadata={"url": profile_url, "handle": handle},
            )
        )

    return SourceScore(
        id=COMMENTS_SOURCE_ID,
        label=COMMENTS_LABEL,
        status=ScoreStatus.AVAILABLE,
        risk_score=float(comments.risk_score),
        findings=tuple(found),
        metadata=metadata,
    )
