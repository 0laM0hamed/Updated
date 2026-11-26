import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { load } from "cheerio";

export async function checkSource(url) {
  const parsedUrl = new URL(url);
  if (parsedUrl.protocol !== "https:" || parsedUrl.hostname !== "erasmus-plus.ec.europa.eu") {
    throw new Error("Only the configured Erasmus+ scholarship page is allowed.");
  }

  const response = await fetch(url, {
    headers: { "User-Agent": "TopicTracker/1.0" },
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    throw new Error(`Scholarship page returned HTTP ${response.status}.`);
  }

  const $ = load(await response.text());
  $("script, style, nav, noscript, iframe, svg").remove();
  const cleanText = $("body").text().replace(/\s+/g, " ").trim();
  if (!cleanText) {
    throw new Error("The scholarship page did not contain readable body text.");
  }

  const hash = createHash("sha256").update(cleanText, "utf8").digest("hex");
  return { url: response.url, clean_text: cleanText, hash };
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
