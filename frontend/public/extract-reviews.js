/**
 * Review extractor — paste this whole file into the DevTools console on any
 * product page that shows reviews, and it prints the verbatim review text.
 *
 * This is the actual mechanism the extension will use. Run it once by hand and
 * the approach stops being abstract: the reviews are already in the page, and
 * we are just reading them.
 *
 * Returns { reviews: string[], via: string } and also sets window.__reviews.
 */
(() => {
  // Widget -> the element that holds one review's text. Order matters only for
  // reporting which one won; we try all of them and keep the best yield.
  const WIDGETS = {
    'judge.me': '.jdgm-rev__body, .jdgm-rev__body p',
    loox: '.loox-review .loox-comment, .loox-review-text',
    yotpo: '.yotpo-review .content-review, .yotpo-main .content-review',
    stamped: '.stamped-review-content-body',
    okendo: '[data-oke-reviews] .oke-reviewContent-body, .oke-reviewContent-body',
    'shopify-native': '.spr-review-content-body',
    'reviews.io': '.ruk_rating_snippet_comment, .R-ReviewsList__item--body',
    trustpilot: '[data-service-review-text-typography]',
    // Amazon renamed this: `review-body` is stale and matches nothing on
    // current pages. `reviewText` is what today's markup uses (verified against
    // a saved amazon.com/dp page). Both kept in case of regional variation.
    amazon: '[data-hook="reviewText"], [data-hook="review-body"] span',
    bazaarvoice: '.bv-content-summary-body-text, .bv-review-content',
  };

  // "Load more reviews" controls, so a caller that can click (the content
  // script, or the Playwright harness) has one table to consult rather than
  // inventing its own. Deliberately generic: the widget-specific classes vary
  // by theme, but the button text does not.
  const LOAD_MORE = [
    '.jdgm-paginate__next-page',
    '.loox-more-reviews, .loox-pagination-next',
    '.yotpo-nav-dropdown-button, .yotpo .pagination-next',
    '.stamped-pagination-next',
    '.oke-showMore-button, .oke-pagination-next',
    '.spr-pagination-next a',
    '[data-hook="pagination-bar"] .a-last a',
  ].join(',');

  // Strip widget chrome that shares the review's text node. Left in, it pollutes
  // what GPTZero scores - measured examples that needed this: '★★★★★"I got
  // exactly what I didn't know...' (darngoodyarn) and "Tango's product reviews5
  // out of 5 starsThe device that just..." (amazon).
  const clean = (s) =>
    (s || '')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/[★☆�]+/g, ' ')
      // Amazon ships screen-reader toggle text inside the review container.
      .replace(/(Brief|Full) content visible, double tap to read (full|brief) content\.?/gi, ' ')
      // Backstop for embedded video players whose classes aren't `vjs-*`, so the
      // structural strip in readText() missed them.
      .replace(/No spoken audio/gi, ' ')
      .replace(/Video Player is loading\.?/gi, ' ')
      .replace(/(Current Time|Duration|Remaining Time)\s*\d+:\d+/gi, ' ')
      .replace(/Loaded:\s*[\d.]+%/gi, ' ')
      .replace(/Stream Type\s*(LIVE)?/gi, ' ')
      .replace(/Playback Rate|Picture-in-Picture|Fullscreen|Chapters|Descriptions/gi, ' ')
      .replace(/(This is|Beginning of) (a )?(modal|dialog) window\.?/gi, ' ')
      .replace(/captions settings, opens captions settings dialog/gi, ' ')
      .replace(/^.{0,40}?\bproduct reviews?\b/i, '')
      .replace(/\b\d(?:\.\d)?\s*out of\s*\d\s*stars?\b/gi, ' ')
      .replace(/^(Verified Purchase|Verified Buyer|Verified Review|Translated from \w+)[:\s-]*/i, '')
      .replace(/\s*(Was this helpful\?|Report abuse|Read more|Show less|Helpful\s*\d*)\s*$/i, '')
      // Leading/trailing quote marks the widget wrapped around the text.
      .replace(/^["“”'\s]+|["“”'\s]+$/g, '')
      .replace(/\s+/g, ' ')
      .trim();

  // Applied after clean(): card metadata is positional, so it needs the
  // whitespace already normalised before the anchored patterns will match.
  const cleanCard = (s) => stripCardChrome(clean(s));

  // Review cards often prepend a metadata block and append a vote counter, and
  // the heuristic path grabs the whole card. Measured on azazie.ca, where every
  // review arrived as:
  //   "s****n United States July 30, 2026 Color: Olive Fit: Right
  //    Size Ordered: A8 Body Shape: Hourglass <the actual review> Helpful (32)"
  // That is ~90-120 chars of boilerplate per review, near-identical across all
  // of them - exactly the kind of shared machine phrasing that skews a detector.
  const MONTH =
    '(?:January|February|March|April|May|June|July|August|September|October|November|December)';
  // Attribute labels used by apparel review widgets. Longest-first so
  // "Size Ordered" wins over "Size".
  const LABEL =
    '(?:Colou?r|Fit|Size Ordered|Size|Body Shape|Overall Fit|Usual Size|Height|Weight|Bust|Waist|Hips?|Age|Style)';
  const PAIR_START = new RegExp(`^${LABEL}\\s*:\\s*`, 'i');
  const PAIR_NEXT = new RegExp(`\\s${LABEL}\\s*:`, 'i');

  /**
   * Strip a leading run of "Label: value" pairs.
   *
   * Walks label to label rather than assuming a word count: a value ends where
   * the next label begins. A fixed 1-word rule splits "Color: Lemon Sorbet", and
   * a 2-word rule eats the first word of the review after the final pair.
   */
  const stripAttrPairs = (s) => {
    while (PAIR_START.test(s)) {
      s = s.replace(PAIR_START, '');
      const next = s.match(PAIR_NEXT);
      if (next) {
        s = s.slice(next.index + 1); // value ran up to the next label
      } else {
        s = s.replace(/^\S+\s*/, ''); // final pair: value is a single token
        break;
      }
    }
    return s;
  };

  /** Strip review-card chrome that the widget selectors don't exclude. */
  const stripCardChrome = (s) =>
    stripAttrPairs(
      // masked reviewer handle + country + posting date
      s.replace(
        new RegExp(`^\\S*\\*{2,}\\S*\\s+.{0,40}?\\b${MONTH}\\s+\\d{1,2},\\s*\\d{4}\\s*`, 'i'),
        '',
      ),
    )
      // trailing vote counter: "Helpful (32)", "Helpful 32"
      .replace(/\s*Helpful\s*\(?\s*\d+\s*\)?\s*$/i, '')
      .trim();

  const keep = (s) => s.length >= 25 && s.length <= 5000;

  // Subtrees that are never review prose but often sit INSIDE a review
  // container. Amazon nests a video.js player in reviews that have a video, and
  // its control-bar text ("No spoken audio", "Video Player is loading.", "Current
  // Time 0:00", "Loaded: 13.35%") lands in textContent ahead of the actual
  // review. That string is machine text, so GPTZero scores it as AI - a review
  // with a video attached would cast a false 'AI' vote.
  const JUNK_SUBTREE = [
    'video', 'audio', 'script', 'style', 'noscript', 'template', 'svg',
    'button', 'select', 'option', 'form', 'input',
    '[aria-hidden="true"]',
    // video.js and other embedded players
    '[class*="vjs-"]', '[class*="video-player"]', '[class*="videoPlayer"]',
    '[class*="media-player"]', '[class*="mediaPlayer"]', '[class*="airy-"]',
    '[data-hook="review-image-tile-section"]',
  ].join(',');

  /**
   * Read an element's prose. Clones first so stripping junk never mutates the
   * live page - the extension must be a pure reader.
   */
  const readText = (el) => {
    let node;
    try {
      node = el.cloneNode(true);
    } catch {
      return el.textContent; // clone unsupported: fall back to the raw read
    }
    for (const junk of node.querySelectorAll?.(JUNK_SUBTREE) ?? []) junk.remove();
    return node.textContent;
  };

  /** Every document we can reach: the page plus any same-origin iframes. */
  const docs = () => {
    const out = [document];
    for (const f of document.querySelectorAll('iframe')) {
      try {
        if (f.contentDocument) out.push(f.contentDocument);
      } catch {
        /* cross-origin iframe: a content script with all_frames handles it */
      }
    }
    return out;
  };

  // --- source 1: JSON-LD (works server-side too, ~8% of stores) -------------
  const fromJsonLd = () => {
    const found = [];
    const walk = (node) => {
      if (!node || typeof node !== 'object') return;
      if (Array.isArray(node)) return node.forEach(walk);
      if (node.reviewBody) found.push(String(node.reviewBody));
      for (const v of Object.values(node)) walk(v);
    };
    for (const d of docs())
      for (const tag of d.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          walk(JSON.parse(tag.textContent));
        } catch {
          /* malformed JSON-LD is common; skip it */
        }
      }
    return found;
  };

  // --- source 2: microdata --------------------------------------------------
  const fromMicrodata = () =>
    docs().flatMap((d) =>
      [...d.querySelectorAll('[itemprop="reviewBody"], [itemprop="description"][itemscope]')].map(
        readText,
      ),
    );

  // --- source 3: known widget selectors (the workhorse) --------------------
  const fromWidgets = () => {
    const hits = {};
    for (const [name, sel] of Object.entries(WIDGETS)) {
      const texts = docs()
        .flatMap((d) => [...d.querySelectorAll(sel)])
        .map(readText);
      const good = [...new Set(texts.map(cleanCard).filter(keep))];
      if (good.length) hits[name] = good;
    }
    return hits;
  };

  // --- source 4: gated heuristic for an unrecognised widget ----------------
  //
  // MEASURED: the original permissive version of this was 0-for-14 on saved
  // pages. It returned CSS rules (`#ProductImage { max-width: 335px }`), product
  // carousels ("Quick View Brown Leather Bound Sketchbook"), and Cloudflare's
  // "Verifying your connection...". All of that is marketing or machine text,
  // i.e. exactly the input GPTZero flags as AI - a false-verdict generator.
  //
  // So this now refuses unless the container looks like a review list:
  //   - never inside <style>/<script>/<template>/<noscript>
  //   - the container's own class/id mentions review
  //   - the text reads like a person, not like a product tile
  // It returns [] rather than a guess. "No reviews found" is a correct answer;
  // a plausible-looking wrong corpus is not.
  const EXCLUDE = new Set(['STYLE', 'SCRIPT', 'TEMPLATE', 'NOSCRIPT', 'SVG', 'HEAD']);
  const inExcluded = (el) => {
    for (let n = el; n; n = n.parentElement) if (EXCLUDE.has(n.tagName)) return true;
    return false;
  };
  // Product-tile / chrome tells. Any hit disqualifies the text.
  const NOT_REVIEW =
    /(\{|\}|max-width:|font-size:|@media|Quick (View|Add)|Regular price|Unit price|Add to (cart|bag)|Sold out|Verifying your connection|Please wait|Pause slideshow|Choose options|Select options|Wähle eine Kollektion)/i;
  // Review-ish tells: first person, or an opinion verb.
  const IS_REVIEW = /\b(I|my|me|we|our|ordered|bought|purchased|received|returned|arrived|love|hate|disappointed|recommend|quality|fits?|shipping)\b/i;

  const fromHeuristic = () => {
    let best = [];
    for (const d of docs()) {
      const parents = new Map();
      for (const el of d.querySelectorAll('p, div, span, li, blockquote')) {
        if (inExcluded(el)) continue;
        const t = cleanCard(readText(el));
        if (!keep(t) || el.children.length > 3) continue;
        if (!/[.!?]/.test(t)) continue;
        if (NOT_REVIEW.test(t) || !IS_REVIEW.test(t)) continue;
        const p = el.parentElement;
        if (!p) continue;
        if (!parents.has(p)) parents.set(p, []);
        parents.get(p).push(t);
      }
      for (const [p, texts] of parents) {
        // The container must self-identify as reviews. Without this the best
        // candidate is usually a product grid that happens to use prose.
        const ctx = `${p.className || ''} ${p.id || ''} ${p.getAttribute('data-testid') || ''}`;
        if (!/review|rating|testimonial|comment|feedback/i.test(ctx)) continue;
        const uniq = [...new Set(texts)];
        if (uniq.length >= 3 && uniq.length > best.length) best = uniq;
      }
    }
    return best;
  };

  // --- run the cascade -----------------------------------------------------
  const ld = [...new Set(fromJsonLd().map(cleanCard).filter(keep))];
  const md = [...new Set(fromMicrodata().map(cleanCard).filter(keep))];
  const widgets = fromWidgets();

  const widgetTotal = Object.values(widgets).flat();
  let reviews, via;

  if (widgetTotal.length >= 3) {
    reviews = [...new Set(widgetTotal)];
    via = 'widget:' + Object.keys(widgets).join('+');
  } else if (ld.length >= 3) {
    reviews = ld;
    via = 'json-ld';
  } else if (md.length >= 3) {
    reviews = md;
    via = 'microdata';
  } else if (widgetTotal.length || ld.length || md.length) {
    reviews = [...new Set([...widgetTotal, ...ld, ...md])];
    via = 'mixed-thin';
  } else {
    reviews = fromHeuristic();
    // Distinguish "guessed something" from "found nothing" — the caller must be
    // able to report no-reviews rather than score a guess.
    via = reviews.length ? 'heuristic' : 'none';
  }

  // --- report --------------------------------------------------------------
  console.log(`%cExtracted ${reviews.length} review(s) via ${via}`,
    'font-weight:bold;font-size:13px');
  const detected = Object.keys(WIDGETS).filter((n) =>
    document.documentElement.innerHTML.toLowerCase().includes(n.replace(/[.-]/g, '')),
  );
  console.log('widgets referenced in page:', detected.join(', ') || '(none detected)');
  console.log('per-source yield:', {
    'json-ld': ld.length, microdata: md.length,
    ...Object.fromEntries(Object.entries(widgets).map(([k, v]) => [k, v.length])),
  });
  console.table(reviews.map((t, i) => ({ '#': i, chars: t.length, text: t.slice(0, 90) })));
  if (via === 'heuristic')
    console.warn('Heuristic fallback: verify these are really reviews before trusting a verdict.');

  window.__reviews = reviews;
  console.log('Full strings in window.__reviews — copy with: copy(JSON.stringify(window.__reviews))');
  // `loadMore` is handed back so an automated caller pages the list with the
  // same selectors the extractor ships with, instead of a parallel table.
  return { reviews, via, loadMore: LOAD_MORE };
})();
