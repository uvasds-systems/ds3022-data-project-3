# config.py

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# SEC Headers for polite requests
SEC_HEADERS = {
    "User-Agent": "ds3022-sec-ai-trends/1.0 (xqd7aq@virginia.edu)",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "*/*",
    "Connection": "keep-alive",
}

# Filing Filters and some filters
FORMS_TO_INCLUDE = ["10-K", "10-Q", "20-F", "40-F", "6-K", "8-K"]

START_YEAR = 2015
END_YEAR = 2025

SEC_SLEEP = 0.2  # polite crawl delay between SEC requests

# AI Text Detection

# Minimum words for a paragraph to be considered 
PARAGRAPH_MIN_WORDS = 15

# Keywords that count as AI related
AI_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "neural networks",
    "large language model",
    "large language models",
    "llm",
    "llms",
    "generative ai",
    "gen ai",
    "foundation model",
    "foundation models",
    "computer vision",
    "reinforcement learning",
    "ai-powered",
    "ai powered",
    "ai-driven",
    "ai driven",
    "predictive analytics",
    "algorithmic trading",
]

# Tech and energy companies to analyze
COMPANIES = [
    # Tech
    {"ticker": "AAPL", "cik": "0000320193", "sector": "Tech"},
    {"ticker": "MSFT", "cik": "0000789019", "sector": "Tech"},
    {"ticker": "GOOGL", "cik": "0001652044", "sector": "Tech"},
    {"ticker": "AMZN", "cik": "0001018724", "sector": "Tech"},
    {"ticker": "META", "cik": "0001326801", "sector": "Tech"},
    {"ticker": "NVDA", "cik": "0001045810", "sector": "Tech"},
    {"ticker": "AMD", "cik": "0000002488", "sector": "Tech"},
    {"ticker": "AVGO", "cik": "0001730168", "sector": "Tech"},
    {"ticker": "CRM", "cik": "0001108524", "sector": "Tech"},
    {"ticker": "ORCL", "cik": "0001341439", "sector": "Tech"},
    {"ticker": "IBM", "cik": "0000051143", "sector": "Tech"},
    {"ticker": "INTC", "cik": "0000050863", "sector": "Tech"},
    {"ticker": "ADBE", "cik": "0000796343", "sector": "Tech"},
    {"ticker": "CSCO", "cik": "0000858877", "sector": "Tech"},
    {"ticker": "SNOW", "cik": "0001640147", "sector": "Tech"},

    # Energy
    {"ticker": "XOM", "cik": "0000034088", "sector": "Energy"},
    {"ticker": "CVX", "cik": "0000093410", "sector": "Energy"},
    {"ticker": "SLB", "cik": "0000087347", "sector": "Energy"},
    {"ticker": "OXY", "cik": "0000797468", "sector": "Energy"},
    {"ticker": "BP",  "cik": "0000313807", "sector": "Energy"},
    {"ticker": "SHEL","cik": "0001306965", "sector": "Energy"},
    {"ticker": "COP", "cik": "0001163165", "sector": "Energy"},
    {"ticker": "EOG", "cik": "0000821189", "sector": "Energy"},
    {"ticker": "PBR", "cik": "0001161683", "sector": "Energy"},
    {"ticker": "HAL", "cik": "0000045012", "sector": "Energy"},
    {"ticker": "KMI", "cik": "0001506307", "sector": "Energy"},
    {"ticker": "ENB", "cik": "0000378249", "sector": "Energy"},
    {"ticker": "EPD", "cik": "0001061219", "sector": "Energy"},
    {"ticker": "NE",  "cik": "0000314808", "sector": "Energy"},
    {"ticker": "OKLO","cik": "0001849056", "sector": "Energy"},
]

# Convenience Maps
TICKER_TO_CIK = {c["ticker"]: c["cik"] for c in COMPANIES}
TICKER_TO_SECTOR = {c["ticker"]: c["sector"] for c in COMPANIES}

# duckdb path
DUCKDB_PATH = PROCESSED_DIR / "sec_ai.duckdb"