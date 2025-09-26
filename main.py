import asyncio
import sys
import time
from pathlib import Path
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy

# try to import SmartScrapingStrategy (if available)
try:
    from crawl4ai.content_scraping_strategy import SmartScrapingStrategy
    SMART_AVAILABLE = True
except Exception:
    SMART_AVAILABLE = False

# optional: trafilatura for better article extraction
try:
    import trafilatura
    TRAFI_AVAILABLE = True
except Exception:
    TRAFI_AVAILABLE = False

from lxml.html import fromstring


def extract_readable_text(html: str) -> str:
    """Try trafilatura, else fallback to lxml text extraction."""
    if not html:
        return ""
    if TRAFI_AVAILABLE:
        try:
            txt = trafilatura.extract(html)
            if txt:
                return txt.strip()
        except Exception:
            pass
    # fallback: lxml text content (keeps paragraphs, strips whitespace)
    try:
        doc = fromstring(html)
        text = doc.text_content()
        # normalize whitespace and remove empty lines
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n\n".join(lines)
    except Exception:
        # final fallback: return raw (shortened) HTML
        return html.strip()


async def main():
    scraping_strategy = SmartScrapingStrategy() if SMART_AVAILABLE else LXMLWebScrapingStrategy()

    config = CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=1, include_external=False),
        scraping_strategy=scraping_strategy,
        verbose=True
    )

    start_time = time.time()

    async with AsyncWebCrawler(concurrency=3) as crawler:
        results = await crawler.arun("https://www.wikipedia.org", config=config)

    elapsed = time.time() - start_time
    print(f"\nCrawled {len(results)} pages in {elapsed:.2f} seconds")

    output = []
    for r in results:
        url = getattr(r, "url", None) or str(r)
        depth = (r.metadata.get("depth") if getattr(r, "metadata", None) else None)

        # Preferred: already-extracted markdown (if strategy produced it)
        md = getattr(r, "markdown", None)
        if md:
            content = md
        else:
            # fallback: try raw html attribute
            html = getattr(r, "html", None)
            if html:
                content = extract_readable_text(html)
            else:
                # last resort: try r.data dict or empty string
                data = getattr(r, "data", None)
                if isinstance(data, dict):
                    # try common keys
                    content = data.get("content") or data.get("text") or ""
                    if content and content.strip().startswith("<"):
                        # if it's HTML, try extracting readable text
                        content = extract_readable_text(content)
                else:
                    content = ""

        output.append({
            "url": url,
            "depth": depth,
            "content": content
        })

    # ---- SAVE AS MARKDOWN ----
    out_path = Path("crawl_results.md")
    with out_path.open("w", encoding="utf-8") as f:
        for idx, item in enumerate(output, start=1):
            f.write(f"# Page {idx}\n")
            f.write(f"**URL:** {item['url']}\n\n")
            if item['depth'] is not None:
                f.write(f"**Depth:** {item['depth']}\n\n")
            f.write("## Content\n\n")
            f.write(item['content'] if item['content'] else "_(No content extracted)_")
            f.write("\n\n---\n\n")

    print(f"Saved {len(output)} items to {out_path.resolve()}")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
