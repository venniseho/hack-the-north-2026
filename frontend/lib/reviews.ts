/**
 * Pull review text out of the user's active tab.
 *
 * The backend cannot do this itself. A headless browser inherits exactly the
 * anti-bot wall the user's own tab walks past — Cloudflare challenges, captchas
 * and 403s all target automated clients specifically (measured across 40
 * domains in docs/ai-review-detection.md). The tab is already past all of it,
 * so the tab is where extraction has to happen.
 *
 * The extractor itself is `public/extract-reviews.js`, injected verbatim rather
 * than ported to TypeScript. That file is also what research/pipeline.py reads
 * and what you paste into DevTools, so there is exactly one copy of the
 * extraction logic and no way for the shipped version to drift from the
 * measured one. It is a self-executing IIFE, which makes its return value the
 * script's completion value — which is what executeScript hands back.
 */

/** Shape returned by public/extract-reviews.js. */
export interface Extraction {
  reviews: string[];
  via: string;
  loadMore: string;
}

export interface ExtractionResult {
  reviews: string[];
  /** Best extraction source across frames, or 'none'. */
  via: string;
  framesWithReviews: number;
  /** Set when injection was impossible (restricted page, CSP, no tab). */
  error?: string;
}

// Served from public/, so it lands at the extension root untouched by the
// bundler - the byte-identical file pipeline.py measures.
const EXTRACTOR_FILE = '/extract-reviews.js' as const;

/**
 * Worst to best. Mirrors VIA_RANK in research/ai-review-detection/pipeline.py:
 * the backend caps confidence for 'heuristic', 'json-ld' and 'mixed-thin', so
 * the label that describes the merged corpus has to be the weakest-honest one,
 * never the most flattering.
 */
const VIA_RANK = ['none', 'heuristic', 'mixed-thin', 'microdata', 'json-ld'];

function viaRank(via: string): number {
  // Any recognised widget outranks everything else.
  if (via.startsWith('widget:')) return VIA_RANK.length;
  const index = VIA_RANK.indexOf(via);
  return index === -1 ? 0 : index;
}

/**
 * Run the extractor in every frame of `tabId` and merge what comes back.
 *
 * Injecting into all frames is the point: Judge.me and Yotpo often render into
 * a cross-origin iframe, which page-level JavaScript cannot read but a content
 * script can. Frames that fail (detached, restricted) are skipped rather than
 * failing the whole extraction.
 */
export async function extractReviewsFromTab(tabId: number): Promise<ExtractionResult> {
  let injections: { result?: unknown }[];

  try {
    injections = await browser.scripting.executeScript({
      target: { tabId, allFrames: true },
      files: [EXTRACTOR_FILE],
    });
  } catch (cause) {
    // Chrome refuses injection on chrome://, the web store, PDF viewers and
    // pages whose CSP blocks it. Not an error worth failing analysis over -
    // every other source still has something to say.
    return {
      reviews: [],
      via: 'none',
      framesWithReviews: 0,
      error: cause instanceof Error ? cause.message : 'script injection failed',
    };
  }

  const seen = new Set<string>();
  const reviews: string[] = [];
  let via = 'none';
  let framesWithReviews = 0;

  for (const injection of injections) {
    const result = injection?.result as Extraction | undefined;
    if (!result?.reviews?.length) continue;

    framesWithReviews += 1;
    if (viaRank(result.via) > viaRank(via)) via = result.via;

    for (const review of result.reviews) {
      // Same-origin iframes get read twice (the extractor walks them itself,
      // and they are also injected as frames), so dedupe here. The backend
      // dedupes again on normalised text - this is just to keep the payload
      // small.
      if (seen.has(review)) continue;
      seen.add(review);
      reviews.push(review);
    }
  }

  return { reviews, via, framesWithReviews };
}

/** Extract from the active tab, if there is one we can inject into. */
export async function extractReviewsFromActiveTab(
  tabId: number | undefined,
): Promise<ExtractionResult> {
  if (tabId === undefined) {
    return { reviews: [], via: 'none', framesWithReviews: 0, error: 'no active tab' };
  }
  return extractReviewsFromTab(tabId);
}
