from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..agent.agent import research_store
from ..scoring.sources.reddit import score_reddit
from .analysis import create_analysis
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
    findings = await research_store(request.current_url)
    return create_analysis(request.current_url, score_reddit(findings))
