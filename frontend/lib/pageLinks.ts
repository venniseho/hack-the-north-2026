/**
 * Runs inside the page, so it can't reference anything outside itself: it is
 * serialized and executed in the tab's context. Reads the live DOM, which is
 * why it works on stores that block the backend's own fetch and on footers
 * built by JavaScript.
 */
function readInstagramLinksFromPage(): string[] {
  const urls = new Set<string>();

  document
    .querySelectorAll<HTMLAnchorElement>('a[href*="instagram.com"]')
    .forEach((anchor) => urls.add(anchor.href));

  // Structured data ("sameAs") often lists social profiles even when the
  // visible footer icons are rendered some other way.
  document
    .querySelectorAll('script[type="application/ld+json"]')
    .forEach((script) => {
      // JSON often escapes slashes (https:\/\/instagram.com\/shop), so the path
      // is matched as a run of segments that may each start with `\/`.
      const matches = script.textContent?.match(
        /https?:\\?\/\\?\/(?:www\.)?instagram\.com(?:\\?\/[^"'\s\\/]*)*/g,
      );
      matches?.forEach((match) => urls.add(match.replace(/\\/g, '')));
    });

  return [...urls].slice(0, 50);
}

/**
 * Instagram links found on the given tab's page, or [] if the page can't be
 * read (chrome:// pages, the Web Store, PDFs, a tab that navigated away).
 * The backend can find the account on its own, so this is only a shortcut and
 * must never block a scan.
 */
export async function collectInstagramLinks(tabId: number | undefined): Promise<string[]> {
  if (tabId === undefined) return [];

  try {
    const [injection] = await browser.scripting.executeScript({
      target: { tabId },
      func: readInstagramLinksFromPage,
    });
    return Array.isArray(injection?.result) ? injection.result : [];
  } catch (error) {
    console.warn('Could not read Instagram links from the page', error);
    return [];
  }
}
