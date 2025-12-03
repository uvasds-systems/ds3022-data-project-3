# src/sec_fetch.py

import json
import time
from pathlib import Path
from typing import List, Dict

import requests

# Import config values
from config import (
    COMPANIES,
    TICKER_TO_CIK,
    TICKER_TO_SECTOR,
    RAW_DIR,
    SEC_HEADERS,
    FORMS_TO_INCLUDE,
    START_YEAR,
    END_YEAR,
    SEC_SLEEP,
)

# Base for SEC submissions API
SUBMISSIONS_BASE = "https://data.sec.gov/submissions/CIK"


def pad_cik(cik: str) -> str:
    """
    Ensure CIK is 10 digits with leading zeros.
    """
    return str(cik).zfill(10)


def build_filing_url(cik: str, accession: str, primary_doc: str) -> str:
    """
    Build an EDGAR filing URL using CIK, accession number, and primary document.
    """
    # Strip leading zeros for the path portion
    cik_no_leading = str(int(cik))

    # Remove dashes from accession to match EDGAR path convention
    acc_nodash = accession.replace("-", "")

    # Guard against missing primary_doc
    if not primary_doc:
        # In a worst case, return directory level URL
        return f"https://www.sec.gov/Archives/edgar/data/{cik_no_leading}/{acc_nodash}/"

    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_leading}/{acc_nodash}/{primary_doc}"
    )


def in_year_range(date_str: str) -> bool:
    """
    Check if a filing date 'YYYY-MM-DD' is within START_YEAR..END_YEAR.
    """
    try:
        year = int(date_str.split("-")[0])
    except Exception:
        return False
    return START_YEAR <= year <= END_YEAR


def get_company_universe(min_per_sector: int | None = None) -> List[Dict]:
    """
    Build a list of company dicts {ticker, cik, sector} from config.COMPANIES.

    min_per_sector is kept for compatibility with the Prefect flow
    but is not enforced here.
    """
    universe: List[Dict] = []

    # Loop over configured companies to construct a clean universe
    for c in COMPANIES:
        # Basic defensive access to keys
        ticker = c.get("ticker")
        cik = c.get("cik")
        sector = c.get("sector")

        if not (ticker and cik and sector):
            print(f"[WARN] Skipping malformed company record: {c}")
            continue

        # Keep config maps as source of truth when present
        if ticker in TICKER_TO_CIK:
            cik = TICKER_TO_CIK[ticker]
        if ticker in TICKER_TO_SECTOR:
            sector = TICKER_TO_SECTOR[ticker]

        universe.append(
            {
                "ticker": str(ticker),
                "cik": str(cik),
                "sector": str(sector),
            }
        )

    print(f"[INFO] Company universe size: {len(universe)}")
    return universe


def fetch_submissions_for_company(cik: str) -> Dict:
    """
    Call the SEC submissions API for a single company and return parsed JSON.
    """
    # Build submissions endpoint for this CIK
    cik_padded = pad_cik(cik)
    url = f"{SUBMISSIONS_BASE}{cik_padded}.json"

    print(f"[DEBUG] Fetching submissions URL={url}")
    print(f"[DEBUG] Using headers={SEC_HEADERS}")

    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.HTTPError:
        # Re-raise HTTPError so caller can distinguish
        raise
    except Exception as e:
        # Wrap unexpected network errors
        raise RuntimeError(f"Network error calling SEC for CIK {cik_padded}: {e}") from e

    text = resp.text
    print(f"[DEBUG] Response: status={resp.status_code}, len(body)={len(text)}")

    try:
        data = resp.json()
    except ValueError as e:
        # If JSON cannot be parsed, surface a clear error
        raise RuntimeError(f"Invalid JSON from SEC for CIK {cik_padded}: {e}") from e

    return data


def extract_filings_for_company(ticker: str, cik: str, sector: str, data: Dict) -> List[Dict]:
    """
    From the submissions JSON, extract filings matching our forms and date range.

    Returns a list of filing dicts.
    """
    # Navigate into the "recent" filings block, tolerate missing keys
    filings_block = data.get("filings", {}).get("recent", {})
    forms = filings_block.get("form", []) or []
    dates = filings_block.get("filingDate", []) or []
    accessions = filings_block.get("accessionNumber", []) or []
    primary_docs = filings_block.get("primaryDocument", []) or []

    # Ensure lists are aligned by taking the smallest length
    n = min(len(forms), len(dates), len(accessions), len(primary_docs))
    results: List[Dict] = []

    if n == 0:
        print(f"[WARN] No recent filings found in JSON for {ticker} (CIK={cik})")
        return results

    # Loop over each filing index and apply filters
    for i in range(n):
        form = forms[i]
        filing_date = dates[i]
        accession = accessions[i]
        primary_doc = primary_docs[i]

        # Keep only desired form types
        if form not in FORMS_TO_INCLUDE:
            continue

        # Filter by configured year range
        if not in_year_range(filing_date):
            continue

        # Build a direct URL to the filing document
        try:
            filing_url = build_filing_url(cik, accession, primary_doc)
        except Exception as e:
            print(
                f"[WARN] Failed to build URL for {ticker} {form} {filing_date}: {e}"
            )
            continue

        # Append cleaned record
        results.append(
            {
                "ticker": ticker,
                "cik": pad_cik(cik),
                "sector": sector,
                "form": form,
                "filing_date": filing_date,
                "accession": accession,
                "primary_doc": primary_doc,
                "filing_url": filing_url,
            }
        )

    return results


def run_fetch(min_per_sector: int | None = None) -> str:
    """
    Main entry point used by Prefect.

    1. Build the company universe from config.
    2. For each company, call the submissions API.
    3. Filter by form type and year range.
    4. Write a single JSON index file with all filings.

    Returns:
        Path to the JSON index as a string.
    """
    # Ensure raw directory exists before writing
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Construct company universe from config
    companies = get_company_universe(min_per_sector=min_per_sector)

    all_filings: List[Dict] = []

    # Loop over each company and collect filings
    for c in companies:
        ticker = c["ticker"]
        cik = c["cik"]
        sector = c["sector"]

        print(f"[INFO] Fetching filings for {ticker} CIK={cik}")

        # Call submissions API and handle network and HTTP errors
        try:
            data = fetch_submissions_for_company(cik)
        except requests.HTTPError as e:
            print(
                f"[WARN] Failed to fetch submissions for {ticker} "
                f"({pad_cik(cik)}): {e}"
            )
            continue
        except Exception as e:
            print(
                f"[WARN] Unexpected error fetching submissions for {ticker} "
                f"({pad_cik(cik)}): {e}"
            )
            continue

        # Extract the subset of filings that match forms and date filter
        filings = extract_filings_for_company(ticker, cik, sector, data)
        print(f"[INFO] Collected {len(filings)} filings for {ticker}")
        all_filings.extend(filings)

        # Be polite to SEC servers
        time.sleep(SEC_SLEEP)

    # Fail clearly if nothing was collected
    if not all_filings:
        raise RuntimeError("No filings collected for any ticker")

    # Write combined index to JSON
    index_path = RAW_DIR / "sec_filings_index.json"
    try:
        with index_path.open("w", encoding="utf-8") as f:
            json.dump(all_filings, f, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to write filings index to {index_path}: {e}") from e

    print(f"[INFO] Wrote filings index to {index_path}")
    print(f"[INFO] Total filings indexed: {len(all_filings)}")

    return str(index_path)


if __name__ == "__main__":
    path = run_fetch()
    print(f"Index written to: {path}")