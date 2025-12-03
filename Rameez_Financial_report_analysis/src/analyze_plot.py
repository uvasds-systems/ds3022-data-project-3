# src/analyze_plot.py

import duckdb
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # render to file, no GUI
import matplotlib.pyplot as plt
import pandas as pd

from config import DUCKDB_PATH, BASE_DIR


def run_analysis(window_start: int = 2015, window_end: int = 2025) -> Path:
    """
    Read AI paragraph data from DuckDB, aggregate in different ways,
    and create multiple plots:

      1. AI paragraphs per year by sector (line plot)
      2. Top tickers by total AI paragraphs (bar chart)
      3. AI paragraph counts by form and sector (bar chart)
      4. Sector share (%) of AI paragraphs per year (line plot)
      5. Average AI paragraph length (word count) per year by sector (line plot)

    Returns:
        Path to the main sector trend plot PNG.
    """

    # Basic sanity check that the DuckDB file exists
    print(f"[ANALYZE] Connecting to DuckDB at {DUCKDB_PATH}")
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(
            f"DuckDB database not found at {DUCKDB_PATH}. "
            "Run load_duckdb.py first to create it."
        )

    # Ensure there is a place to write plots
    plots_dir = BASE_DIR / "plots"
    try:
        plots_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Could not create plots directory {plots_dir}: {e}") from e

    # Try to connect to DuckDB
    try:
        con = duckdb.connect(str(DUCKDB_PATH))
    except Exception as e:
        raise RuntimeError(f"Could not open DuckDB at {DUCKDB_PATH}: {e}") from e

    try:
        # Query 1 - aggregate counts by year and sector for main trend plot
        query_year_sector = """
            SELECT
                year,
                sector,
                COUNT(*) AS ai_paragraph_count
            FROM ai_paragraphs
            WHERE year BETWEEN ? AND ?
            GROUP BY year, sector
            ORDER BY year, sector
        """
        try:
            df_year_sector = con.execute(
                query_year_sector, [window_start, window_end]
            ).df()
        except Exception as e:
            raise RuntimeError(
                "Failed to aggregate AI paragraphs by year and sector from DuckDB."
            ) from e

        if df_year_sector.empty:
            raise ValueError(
                f"No rows returned from DuckDB for years {window_start}–{window_end}. "
                "Check that ai_paragraphs was loaded correctly."
            )

        print("[ANALYZE] Aggregated (year, sector) head:")
        print(df_year_sector.head())

        # Plot 1 - AI paragraphs per year by sector (line plot)
        pivot_year_sector = df_year_sector.pivot(
            index="year",
            columns="sector",
            values="ai_paragraph_count",
        ).fillna(0)

        fig1, ax1 = plt.subplots(figsize=(8, 5))
        pivot_year_sector.plot(ax=ax1)

        ax1.set_title("AI related paragraphs per year by sector")
        ax1.set_xlabel("Year")
        ax1.set_ylabel("Count of AI related paragraphs")
        ax1.grid(True, linestyle="--", alpha=0.5)
        ax1.legend(title="Sector")

        fig1.tight_layout()
        path_trends = plots_dir / "ai_trends_by_sector.png"
        fig1.savefig(path_trends)
        plt.close(fig1)
        print(f"[ANALYZE] Saved sector trend plot to {path_trends}")

        # Query 2 - top tickers by total AI paragraphs in the window
        query_top_tickers = """
            SELECT
                ticker,
                sector,
                COUNT(*) AS ai_paragraph_count
            FROM ai_paragraphs
            WHERE year BETWEEN ? AND ?
            GROUP BY ticker, sector
            ORDER BY ai_paragraph_count DESC
            LIMIT 15
        """
        try:
            df_top = con.execute(query_top_tickers, [window_start, window_end]).df()
        except Exception as e:
            print(
                f"[WARN] Failed to compute top tickers for {window_start}-{window_end}: {e}"
            )
            df_top = pd.DataFrame()

        # Plot 2 - Top tickers by total AI paragraphs (bar chart)
        if not df_top.empty:
            # Sort from smallest to largest for a clean horizontal bar chart
            df_top_sorted = df_top.sort_values("ai_paragraph_count", ascending=True)

            fig2, ax2 = plt.subplots(figsize=(8, 6))
            ax2.barh(df_top_sorted["ticker"], df_top_sorted["ai_paragraph_count"])

            ax2.set_title("Top 15 tickers by AI related paragraphs")
            ax2.set_xlabel("Count of AI related paragraphs")
            ax2.set_ylabel("Ticker")
            ax2.grid(True, axis="x", linestyle="--", alpha=0.5)

            fig2.tight_layout()
            path_top_tickers = plots_dir / "ai_paragraphs_top_tickers.png"
            fig2.savefig(path_top_tickers)
            plt.close(fig2)
            print(f"[ANALYZE] Saved top tickers plot to {path_top_tickers}")
        else:
            print("[ANALYZE] No data for top tickers in this window.")

        # Query 3 - counts of AI paragraphs by form and sector
        query_form_sector = """
            SELECT
                form,
                sector,
                COUNT(*) AS ai_paragraph_count
            FROM ai_paragraphs
            WHERE year BETWEEN ? AND ?
            GROUP BY form, sector
        """
        try:
            df_form_sector = con.execute(
                query_form_sector, [window_start, window_end]
            ).df()
        except Exception as e:
            print(
                f"[WARN] Failed to aggregate AI paragraphs by form and sector: {e}"
            )
            df_form_sector = pd.DataFrame()

        # Plot 3 - AI paragraphs by form and sector (grouped bar chart)
        if not df_form_sector.empty:
            # Focus on the most common forms to keep the figure readable
            top_forms = (
                df_form_sector.groupby("form")["ai_paragraph_count"]
                .sum()
                .sort_values(ascending=False)
                .head(8)
                .index
            )
            df_form_sector_top = df_form_sector[df_form_sector["form"].isin(top_forms)]

            pivot_form = df_form_sector_top.pivot(
                index="form",
                columns="sector",
                values="ai_paragraph_count",
            ).fillna(0)

            fig3, ax3 = plt.subplots(figsize=(10, 6))
            pivot_form.plot(kind="bar", ax=ax3)

            ax3.set_title("AI related paragraphs by filing form and sector")
            ax3.set_xlabel("Filing form")
            ax3.set_ylabel("Count of AI related paragraphs")
            ax3.grid(True, axis="y", linestyle="--", alpha=0.5)
            ax3.legend(title="Sector")

            fig3.tight_layout()
            path_form_sector = plots_dir / "ai_paragraphs_by_form_and_sector.png"
            fig3.savefig(path_form_sector)
            plt.close(fig3)
            print(f"[ANALYZE] Saved form-by-sector plot to {path_form_sector}")
        else:
            print("[ANALYZE] No form/sector data for this window.")

        # Plot 4 - sector share (%) of AI paragraphs per year
        #         (computed from df_year_sector already in memory)
        df_total_year = (
            df_year_sector.groupby("year")["ai_paragraph_count"]
            .sum()
            .reset_index()
            .rename(columns={"ai_paragraph_count": "ai_paragraph_count_total"})
        )

        df_share = df_year_sector.merge(df_total_year, on="year")
        df_share["share_percent"] = (
            100.0 * df_share["ai_paragraph_count"] / df_share["ai_paragraph_count_total"]
        )

        pivot_share = df_share.pivot(
            index="year",
            columns="sector",
            values="share_percent",
        ).fillna(0)

        fig4, ax4 = plt.subplots(figsize=(8, 5))
        pivot_share.plot(ax=ax4)

        ax4.set_title("Sector share of AI related paragraphs (%)")
        ax4.set_xlabel("Year")
        ax4.set_ylabel("Percent of total AI related paragraphs")
        ax4.grid(True, linestyle="--", alpha=0.5)
        ax4.legend(title="Sector")

        fig4.tight_layout()
        path_share = plots_dir / "ai_sector_share_percent.png"
        fig4.savefig(path_share)
        plt.close(fig4)
        print(f"[ANALYZE] Saved sector share percent plot to {path_share}")

        # Query 4 - average paragraph length (approx word count) by year/sector
        query_lengths = """
            SELECT
                year,
                sector,
                AVG(LENGTH(paragraph) - LENGTH(REPLACE(paragraph, ' ', '')) + 1)
                    AS avg_word_count
            FROM ai_paragraphs
            WHERE year BETWEEN ? AND ?
            GROUP BY year, sector
            ORDER BY year, sector
        """
        try:
            df_lengths = con.execute(query_lengths, [window_start, window_end]).df()
        except Exception as e:
            print(
                f"[WARN] Failed to compute average paragraph length by sector: {e}"
            )
            df_lengths = pd.DataFrame()

        # Plot 5 - average AI paragraph length (words) per year by sector
        if not df_lengths.empty:
            pivot_lengths = df_lengths.pivot(
                index="year",
                columns="sector",
                values="avg_word_count",
            ).fillna(0)

            fig5, ax5 = plt.subplots(figsize=(8, 5))
            pivot_lengths.plot(ax=ax5)

            ax5.set_title("Average AI paragraph length by sector (words)")
            ax5.set_xlabel("Year")
            ax5.set_ylabel("Average word count")
            ax5.grid(True, linestyle="--", alpha=0.5)
            ax5.legend(title="Sector")

            fig5.tight_layout()
            path_lengths = plots_dir / "ai_avg_paragraph_length.png"
            fig5.savefig(path_lengths)
            plt.close(fig5)
            print(f"[ANALYZE] Saved average paragraph length plot to {path_lengths}")
        else:
            print("[ANALYZE] No paragraph length data available for this period.")

    finally:
        # Always close the DuckDB connection, even if something failed above
        con.close()

    # Return main sector trend plot so Prefect can log or use it
    return path_trends


if __name__ == "__main__":
    run_analysis()