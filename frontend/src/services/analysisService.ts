import { insufficientDataAnalysis, mockAnalysis } from '@/src/data/mockAnalysis';
import type { ScamAnalysis } from '@/src/types/analysis';

export interface AnalysisRequest {
  currentUrl?: string;
  mode?: 'standard' | 'insufficient-data';
}

export interface AnalysisService {
  getAnalysis(request?: AnalysisRequest): Promise<ScamAnalysis>;
}

const MOCK_RESPONSE_DELAY_MS = 850;

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export const analysisService: AnalysisService = {
  async getAnalysis(request) {
    await wait(MOCK_RESPONSE_DELAY_MS);

    if (request?.mode === 'insufficient-data') {
      return insufficientDataAnalysis;
    }

    return mockAnalysis;
  },
};
