from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .analysis import create_mock_analysis
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
def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    return create_mock_analysis(request.current_url)
