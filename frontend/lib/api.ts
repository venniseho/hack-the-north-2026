import type { AnalysisApiResponse } from '@/src/types/scoringApi';

const BASE_URL = import.meta.env.WXT_API_BASE_URL ?? 'http://localhost:8000';

export interface AnalyzeRequest {
  currentUrl?: string;
  /** Instagram links read off the page, so the backend needn't fetch it itself. */
  instagramLinks?: string[];
}

export async function requestAnalysis(
  request: AnalyzeRequest = {},
): Promise<AnalysisApiResponse> {
  const response = await fetch(`${BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Backend responded ${response.status}: ${await response.text()}`);
  }

  return (await response.json()) as AnalysisApiResponse;
}
