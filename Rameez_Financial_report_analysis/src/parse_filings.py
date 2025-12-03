# src/parse_filings.py

# ChatGPT (5.1 model) was used to help make this code more efficient with parallel processing. Computing time reduced from over an hour to 15 minutes. 

import json
import re
import time
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Import config values
from config import (
    RAW_DIR,
    PROCESSED_DIR,
    SEC_HEADERS,
    AI_KEYWORDS,
    PARAGRAPH_MIN_WORDS,
)

# Number of parallel workers for fetching + parsing filings
# Keep this moderate to avoid hammering SEC servers.
MAX_WORKERS = 6

# Simple retry settings for network requests
MAX_RETRIES = 2
REQUEST_TIMEOUT = 20

# Cache directory for raw HTML filings
HTML_CACHE_DIR = RAW_DIR / "html_cache"


def clean_html(html: str) -> str:
    """
    Strip scripts and styles, then extract visible text.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/noscript tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse extra whitespace
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_into_paragraphs(text: str):
    """
    Split long text into candidate paragraphs.
    """

    # First split on blank lines
    raw_paras = re.split(r"\n\s*\n", text)
    paras = []

    # Loop over raw paragraph chunks
    for p in raw_paras:
        p = p.strip()
        if not p:
            continue

        # Further split very long chunks on periods and similar markers
        chunks = re.split(r"(?<=[.!?])\s{2,}", p)
        for c in chunks:
            c = c.strip()
            if not c:
                continue
            paras.append(c)

    return paras


def paragraph_contains_ai(paragraph: str):
    """
    Return (bool, matched_keyword) for AI related content.
    """
    lower = paragraph.lower()
    for kw in AI_KEYWORDS:
        if kw in lower:
            return True, kw
    return False, None


def load_index(index_path: Path):
    """
    Load the filings index and return a list of records.
    Handles both list and dict-with-list formats.
    """
    with open(index_path, "r") as f:
        data = json.load(f)

    # Handle a plain list of records
    if isinstance(data, list):
        return data

    # Handle dict with a list under a common key
    if isinstance(data, dict):
        for key in ["filings", "records", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]

        # Fallback: treat all list-like values as records
        all_vals = []
        for v in data.values():
            if isinstance(v, list):
                all_vals.extend(v)
        if all_vals:
            return all_vals

    raise ValueError("Unexpected structure in sec_filings_index.json")


def _cache_path_for_url(url: str) -> Path:
    """
    Compute a stable cache file path for a filing URL.
    """
    HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(url.encode("utf-8")).hexdigest()
    return HTML_CACHE_DIR / f"{h}.html"


def _fetch_html_with_cache(url: str) -> str | None:
    """
    Fetch a filing HTML with a tiny cache and a couple of retries.

    Returns the HTML text or None if it ultimately fails.
    """

    # Check cache first
    cache_path = _cache_path_for_url(url)
    if cache_path.exists():
        try:
            return cache_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[WARN] Failed to read cache {cache_path}: {e}")

    # Not in cache or cache read failed. Do network fetch.
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=SEC_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            html = resp.text

            # Try to write to cache
            try:
                cache_path.write_text(html, encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"[WARN] Failed to write cache {cache_path}: {e}")

            return html

        except Exception as e:
            print(f"[WARN] Fetch attempt {attempt}/{MAX_RETRIES} failed for {url}: {e}")
            # Small sleep between retries to be polite
            time.sleep(0.3)

    # All retries failed
    print(f"[ERROR] Giving up on filing URL after {MAX_RETRIES} attempts: {url}")
    return None


def _process_single_filing(rec: dict, idx: int, total: int) -> list[dict]:
    """
    Process a single filing record and return a list of AI paragraph rows.

    Each row dict has:
      ticker, sector, year, filing_date, form, paragraph, keyword
    """

    rows: list[dict] = []

    # Extract core fields safely
    ticker = rec.get("ticker")
    sector = rec.get("sector")
    form = rec.get("form") or rec.get("form_type")
    filing_date = rec.get("filing_date") or rec.get("filed")
    url = rec.get("filing_url") or rec.get("url")

    # Derive year from record or filing_date
    year = rec.get("year")
    if year is None and filing_date:
        try:
            year = int(str(filing_date)[:4])
        except Exception:
            year = None

    # Skip filings missing required info
    if not (ticker and sector and form and filing_date and url and year):
        if idx <= 5 or idx % 50 == 0:
            print(f"[WARN] Skipping record {idx}/{total} missing required fields")
        return rows

    # Only keep filings in our analysis window
    if year < 2015 or year > 2025:
        return rows

    # Occasionally print progress for this filing
    if idx <= 5 or idx % 25 == 0:
        print(f"[INFO] [{idx}/{total}] Fetching filing {ticker} {form} {filing_date} at {url}")

    # Fetch HTML with cache and retries
    html = _fetch_html_with_cache(url)
    if html is None:
        # Already logged errors inside _fetch_html_with_cache
        return rows

    # Clean HTML and split into paragraphs
    text = clean_html(html)
    paras = split_into_paragraphs(text)

    # Loop over paragraphs and filter for AI related content
    for p in paras:
        # Basic word count filter to drop tiny snippets
        if len(p.split()) < PARAGRAPH_MIN_WORDS:
            continue

        # Check if paragraph contains any AI keyword
        is_ai, kw = paragraph_contains_ai(p)
        if not is_ai:
            continue

        # Append matching paragraph row
        rows.append(
            {
                "ticker": ticker,
                "sector": sector,
                "year": year,
                "filing_date": filing_date,
                "form": form,
                "paragraph": p,
                "keyword": kw,
            }
        )

    return rows


def run_parse(index_path: Path | None = None) -> Path:
    """
    Read sec_filings_index.json, fetch each filing in parallel,
    extract AI related paragraphs, and write:

        data/processed/ai_paragraphs.csv

    Output columns:
        ticker, sector, year, filing_date, form, paragraph, keyword
    """
    # Default index path if not provided
    if index_path is None:
        index_path = RAW_DIR / "sec_filings_index.json"

    print(f"[INFO] Using filings index at {index_path}")
    filings = load_index(index_path)
    total = len(filings)
    print(f"[INFO] Loaded {total} filings from index")

    # Prepare list to collect all AI rows
    all_rows: list[dict] = []

    # Use a thread pool to speed up network plus parsing work
    print(f"[INFO] Starting parallel parse with up to {MAX_WORKERS} workers")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all filings to the executor
        future_to_idx = {
            executor.submit(_process_single_filing, rec, i, total): i
            for i, rec in enumerate(filings, start=1)
        }

        # As futures complete, extend the master row list
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                rows = future.result()
                if rows:
                    all_rows.extend(rows)
            except Exception as e:
                # Catch unexpected errors for a single filing
                print(f"[ERROR] Unexpected error in filing {idx}/{total}: {e}")

    # Convert all rows to a DataFrame
    out_path = PROCESSED_DIR / "ai_paragraphs.csv"
    df = pd.DataFrame(all_rows)

    # Handle the case where no AI paragraphs are found
    if df.empty:
        print("[WARN] No AI related paragraphs found. Writing empty CSV with headers.")
        df = pd.DataFrame(
            columns=[
                "ticker",
                "sector",
                "year",
                "filing_date",
                "form",
                "paragraph",
                "keyword",
            ]
        )

    # Make sure processed directory exists
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Write AI paragraph data to CSV
    df.to_csv(out_path, index=False)
    print(f"[INFO] Wrote {len(df)} AI related paragraphs to {out_path}")

    return out_path


if __name__ == "__main__":
    run_parse()