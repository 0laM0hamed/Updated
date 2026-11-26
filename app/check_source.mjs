import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { load } from "cheerio";
import Parser from "rss-parser";

const parser = new Parser();
const ALLOWED_HOST = "erasmus-plus.ec.europa.eu";
const NOISE_SELECTOR = [
  "script",
  "style",
  "nav",
  "header",
  "footer",
  "aside",
  "noscript",
  "iframe",
  "svg",
  "time",
  '[class*="advert"]',
  '[id*="advert"]',
  '[class*="cookie"]',
  '[id*="cookie"]',
  '[class*="social"]',
  '[class*="share"]',
  '[class*="date"]',
  '[id*="date"]',
].join(", ");

function assertAllowedUrl(value) {
  const parsedUrl = new URL(value);
  if (parsedUrl.protocol !== "https:" || parsedUrl.hostname !== ALLOWED_HOST) {
    throw new Error(`Only HTTPS pages on ${ALLOWED_HOST} are supported.`);
  }
  return parsedUrl;
}

function normalizeText(value) {
  return value.normalize("NFKC")
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join("\n");
}

function createResult(url, kind, cleanText, feedUrl = null, items = []) {
  if (!cleanText) {
    throw new Error("The page did not contain readable content.");
  }
  return {
    url,
    kind,
    feed_url: feedUrl,
    clean_text: cleanText,
    hash: createHash("sha256").update(cleanText, "utf8").digest("hex"),
    items,
  };
}

async function fetchText(url) {
  const response = await fetch(url, {
    headers: {
      Accept: "text/html, application/rss+xml, application/atom+xml, application/xml, text/xml",
      "User-Agent": "TopicTracker/1.0",
    },
    redirect: "follow",
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    throw new Error(`Page returned HTTP ${response.status}.`);
  }
  assertAllowedUrl(response.url);
  return { response, text: await response.text() };
}

function discoverFeedUrls(response, html, pageUrl) {
  const feedUrls = [];
  const linkHeader = response.headers.get("link") ?? "";
  for (const match of linkHeader.matchAll(/<([^>]+)>;\s*rel="?alternate"?[^,]*;\s*type="?application\/(?:rss\+xml|atom\+xml|xml)"?/gi)) {
    feedUrls.push(match[1]);
  }

  const $ = load(html);
  $('link[rel~="alternate"][type]').each((_, element) => {
    const type = ($(element).attr("type") ?? "").toLowerCase();
    const href = $(element).attr("href");
    if (href && /rss|atom|xml/.test(type)) {
      feedUrls.push(new URL(href, pageUrl).href);
    }
  });

  return [...new Set(feedUrls)].filter((url) => {
    try {
      return assertAllowedUrl(url).hostname === new URL(pageUrl).hostname;
    } catch {
      return false;
    }
  });
}

async function readFeed(feedUrl, pageUrl) {
  try {
    const { text } = await fetchText(feedUrl);
    const feed = await parser.parseString(text);
    const items = (feed.items ?? []).map((item) => ({
      title: normalizeText(item.title ?? ""),
      link: item.link ? new URL(item.link, feedUrl).href : pageUrl,
      content: normalizeText(item.contentSnippet ?? item.content ?? item.summary ?? ""),
    })).filter((item) => item.title || item.content);
    if (!items.length) {
      return null;
    }
    const cleanText = items
      .map((item) => [item.title, item.link, item.content].filter(Boolean).join("\n"))
      .join("\n");
    return createResult(pageUrl, "rss", cleanText, feedUrl, items);
  } catch (error) {
    console.warn(`Could not read advertised feed ${feedUrl}: ${error.message}`);
    return null;
  }
}

export async function checkSource(url) {
  assertAllowedUrl(url);
  const { response, text: html } = await fetchText(url);
  const finalUrl = response.url;

  for (const feedUrl of discoverFeedUrls(response, html, finalUrl)) {
    const result = await readFeed(feedUrl, finalUrl);
    if (result) {
      return result;
    }
  }

  const $ = load(html);
  $(NOISE_SELECTOR).remove();
  for (const element of $("*").toArray()) {
    const classAndId = `${$(element).attr("class") ?? ""} ${$(element).attr("id") ?? ""}`.toLowerCase();
    if (/\b(ad|ads|banner|breadcrumb|pagination|related|toolbar)\b/.test(classAndId)) {
      $(element).remove();
    }
  }
  const content = $("main").first().length
    ? $("main").first()
    : $("article").first().length
      ? $("article").first()
      : $('[role="main"]').first().length
        ? $('[role="main"]').first()
        : $("body");
  const blocks = content.find("h1, h2, h3, p, li").toArray()
    .map((element) => normalizeText($(element).text()))
    .filter(Boolean);
  const uniqueBlocks = [...new Set(blocks)];
  const cleanText = uniqueBlocks.length
    ? uniqueBlocks.join("\n")
    : normalizeText(content.text());
  return createResult(finalUrl, "html", cleanText);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const result = await checkSource(process.argv[2]);
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
