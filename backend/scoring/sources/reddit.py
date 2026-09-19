from ...agent.tools.reddit import RedditFindings
from ..types import ScoreStatus, ScoringFinding, SourceScore


def score_reddit(findings: RedditFindings) -> SourceScore:
    """Convert Reddit research into a source score.

    No verified posts is INSUFFICIENT_DATA, not a clean bill of health: a store
    nobody has discussed is unknown, not trustworthy.
    """
    metadata = {"thread_id": findings.thread_id}

    if findings.error:
        return SourceScore(
            id="reddit",
            label="Reddit",
            status=ScoreStatus.ERROR,
            risk_score=None,
            metadata={**metadata, "error": findings.error},
        )

    if not findings.posts or findings.risk_score is None:
        return SourceScore(
            id="reddit",
            label="Reddit",
            status=ScoreStatus.INSUFFICIENT_DATA,
            risk_score=None,
            metadata=metadata,
        )

    return SourceScore(
        id="reddit",
        label="Reddit",
        status=ScoreStatus.AVAILABLE,
        risk_score=float(findings.risk_score),
        findings=tuple(
            ScoringFinding(
                rule_id=f"REDDIT_{post.severity.upper()}",
                title=post.title,
                explanation=post.quote,
                metadata={
                    "url": post.url,
                    "subreddit": post.subreddit,
                    "severity": post.severity,
                },
            )
            for post in findings.posts
        ),
        metadata=metadata,
    )
