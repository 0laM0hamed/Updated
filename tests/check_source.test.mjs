import test from "node:test";
import assert from "node:assert/strict";

import { checkSource } from "../app/check_source.mjs";

const pageUrl = "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters";

function mockResponse(url, body, contentType) {
  const response = new Response(body, {
    status: 200,
    headers: { "content-type": contentType },
  });
  Object.defineProperty(response, "url", { value: url });
  return response;
}

test("HTML extraction removes navigation, date, and advertisement noise", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => mockResponse(
    String(url),
    `<!doctype html>
      <nav>Navigation noise</nav>
      <main>
        <h1>Scholarship updates</h1>
        <p>Applications are open.</p>
        <p class="publication-date">Updated yesterday</p>
        <div class="advertisement">Ad noise</div>
        <script>Script noise</script>
      </main>`,
    "text/html",
  );
  try {
    const first = await checkSource(pageUrl);
    const second = await checkSource(pageUrl);
    assert.equal(first.kind, "html");
    assert.match(first.clean_text, /Scholarship updates/);
    assert.match(first.clean_text, /Applications are open/);
    assert.doesNotMatch(first.clean_text, /Navigation noise|Updated yesterday|Ad noise|Script noise/);
    assert.equal(first.hash, second.hash);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("an advertised RSS feed is used before scraping page text", async () => {
  const originalFetch = globalThis.fetch;
  const feedUrl = "https://erasmus-plus.ec.europa.eu/news/feed.xml";
  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url === pageUrl) {
      return mockResponse(
        url,
        '<link rel="alternate" type="application/rss+xml" href="/news/feed.xml"><main>Page fallback</main>',
        "text/html",
      );
    }
    assert.equal(url, feedUrl);
    return mockResponse(
      url,
      `<?xml version="1.0"?>
        <rss version="2.0"><channel><title>News</title><link>${pageUrl}</link>
          <item><title>New scholarship</title><link>${pageUrl}/new</link>
            <description>Applications open today.</description><pubDate>Mon, 26 Nov 2026 00:00:00 GMT</pubDate>
          </item>
        </channel></rss>`,
      "application/rss+xml",
    );
  };
  try {
    const result = await checkSource(pageUrl);
    assert.equal(result.kind, "rss");
    assert.equal(result.feed_url, feedUrl);
    assert.equal(result.items.length, 1);
    assert.match(result.clean_text, /New scholarship/);
    assert.doesNotMatch(result.clean_text, /Page fallback|2026/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("unsupported hosts are rejected before fetching", async () => {
  await assert.rejects(
    checkSource("https://example.com/scholarships"),
    /Only HTTPS pages on erasmus-plus\.ec\.europa\.eu are supported/,
  );
});
