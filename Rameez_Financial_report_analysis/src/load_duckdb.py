# src/load_duckdb.py

import duckdb
from pathlib import Path
import pandas as pd

from config import PROCESSED_DIR, DUCKDB_PATH


def load_ai_paragraphs_to_duckdb(source_csv: Path | None = None):
    """
    Load ai_paragraphs.csv into a DuckDB database.
    Creates or replaces the ai_paragraphs table.
    """

    # Default to processed/ai_paragraphs.csv if no path is supplied
    if source_csv is None:
        source_csv = PROCESSED_DIR / "ai_paragraphs.csv"

    print(f"[DUCKDB] Loading data from {source_csv}")

    # Confirm the CSV actually exists
    if not source_csv.exists():
        raise FileNotFoundError(
            f"No CSV found at {source_csv}. Ensure parse_filings has been run."
        )

    # Attempt to read the CSV
    try:
        df = pd.read_csv(source_csv)
    except Exception as e:
        raise RuntimeError(f"Failed to read {source_csv}: {e}") from e

    # Validate required columns
    expected_cols = {
        "ticker",
        "sector",
        "year",
        "filing_date",
        "form",
        "paragraph",
        "keyword",
    }
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns in ai_paragraphs.csv: {missing}")

    # Create directory for the DuckDB file
    try:
        DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Unable to create DuckDB directory {DUCKDB_PATH.parent}: {e}")

    # Connect to DuckDB
    try:
        con = duckdb.connect(str(DUCKDB_PATH))
    except Exception as e:
        raise RuntimeError(f"Could not open DuckDB at {DUCKDB_PATH}: {e}")

    try:
        # Drop old table to keep runs reproducible
        con.execute("DROP TABLE IF EXISTS ai_paragraphs")

        # Create main table from dataframe
        con.execute(
            """
            CREATE TABLE ai_paragraphs AS
            SELECT
                CAST(year AS INTEGER) AS year,
                ticker,
                sector,
                filing_date,
                form,
                paragraph,
                keyword
            FROM df
            """
        )

        # Secondary summary table for fast analysis queries
        con.execute("DROP TABLE IF EXISTS ai_counts_year_sector_ticker")
        con.execute(
            """
            CREATE TABLE ai_counts_year_sector_ticker AS
            SELECT
                year,
                sector,
                ticker,
                COUNT(*) AS ai_paragraph_count
            FROM ai_paragraphs
            GROUP BY year, sector, ticker
            """
        )

        print(f"[DUCKDB] Loaded {len(df)} rows into ai_paragraphs")

    except Exception as e:
        raise RuntimeError(f"DuckDB load failed: {e}") from e

    finally:
        # Always close the connection
        con.close()

    print(f"[DUCKDB] Database written to {DUCKDB_PATH}")


if __name__ == "__main__":
    load_ai_paragraphs_to_duckdb()