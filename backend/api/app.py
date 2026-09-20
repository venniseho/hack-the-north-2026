import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..agent.agent import research_store, research_store_instagram
from ..scoring.sources.instagram import score_instagram_comments
from ..scoring.sources.reddit import score_reddit
from .analysis import analyze_reviews, create_analysis
from .models import AnalysisResponse, AnalyzeRequest


app = FastAPI(
    title="Scam Detection Scoring API",
    description="Aggregates transparent source scores into category and overall risk.",
    version="0.1.0",
)

# Local integration uses no credentials. Extension IDs vary between development
# installs, so all origins are allowed until deployment provides a fixed origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    # Both never raise, so one slow or broken source can't fail the request.
    reddit, instagram, gptzero = await asyncio.gather(
        asyncio.gather(
        research_store(request.current_url),
        analyze_reviews(request.reviews, request.via),
    ),
        research_store_instagram(request.current_url, request.instagram_links),
    )
    return create_analysis(
        request.current_url,
        score_reddit(reddit),
        score_instagram_comments(instagram),
    , gptzero)
